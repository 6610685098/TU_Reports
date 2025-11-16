from dataclasses import dataclass
from typing import Any, Dict, List

from django.test import TestCase
from django.test.utils import override_settings
from unittest.mock import MagicMock, patch


from tickets.dispatcher import (
    _to_float,
    haversine_km,
    fast_distance_km,
    bbox_for_radius_km,
    get_active_rule_cached,
    AutoDispatcher,
    DispatchResult,
    PENDING_BUCKET,
    INPROG_BUCKET,
    MAX_TOTAL_OPEN,
    MAX_PENDING,
    MAX_INPROG,
    auto_dispatch_ticket,
)
from tickets import dispatcher

# from tickets.dispatcher import AutoDispatcher, fast_distance_km as real_fast_distance_km
# from tickets.models import Ticket
# from authentication.models import User


# -------------------------------------------------------------------
#  Geo helpers
# -------------------------------------------------------------------


class TestGeoHelpers(TestCase):
    def test_to_float_valid_and_invalid(self):
        """_to_float ต้องแปลงค่าที่ถูกต้อง และคืน None เมื่อแปลงไม่ได้"""
        self.assertEqual(_to_float("1.23"), 1.23)
        self.assertEqual(_to_float(5), 5.0)
        self.assertIsNone(_to_float(None))
        self.assertIsNone(_to_float("not-number"))

    def test_haversine_none_returns_inf(self):
        """ถ้าพิกัดใด ๆ เป็น None ให้คืนระยะเป็น inf"""
        d = haversine_km(None, 100, 13.0, 100.0)
        self.assertEqual(d, float("inf"))

    def test_haversine_basic_distance(self):
        """ระยะ (0,0) → (0,1) ประมาณ 111km"""
        d = haversine_km(0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(d, 111, delta=5)

    def test_fast_distance_none_returns_inf(self):
        """fast_distance_km ถ้ามีพิกัด None → inf"""
        d = fast_distance_km(13.0, None, 14.0, 100.0)
        self.assertEqual(d, float("inf"))

    def test_fast_distance_basic_distance(self):
        """fast_distance_km ต้องได้ค่าประมาณเท่า haversine"""
        d = fast_distance_km(0.0, 0.0, 0.0, 1.0)
        d2 = haversine_km(0.0, 0.0, 0.0, 1.0)
        self.assertGreater(d, 0)
        self.assertAlmostEqual(d, d2, delta=5)

    def test_bbox_for_radius_normal_and_none(self):
        """bbox_for_radius_km: มี lat/lon → คืน bbox, ถ้าไม่มี → None"""
        bbox = bbox_for_radius_km(13.0, 100.0, km=10)
        self.assertIsNotNone(bbox)
        min_lat, max_lat, min_lon, max_lon = bbox
        self.assertLess(min_lat, max_lat)
        self.assertLess(min_lon, max_lon)

        self.assertIsNone(bbox_for_radius_km(None, 100.0, km=10))


# -------------------------------------------------------------------
#  get_active_rule_cached
# -------------------------------------------------------------------


class TestGetActiveRuleCached(TestCase):
    @patch("tickets.dispatcher.cache")
    @patch("tickets.dispatcher.AssignmentRule.get_active_or_default")
    def test_get_active_rule_cached_uses_cache(self, mock_get_active, mock_cache):
        """
        ครั้งแรกไม่มี cache → ต้องเรียก AssignmentRule.get_active_or_default แล้ว cache.set
        ครั้งที่สองมี cache → ต้องไม่เรียก DB ซ้ำ
        """
        rule = object()

        # call แรก: cache.get -> None
        mock_cache.get.return_value = None
        mock_get_active.return_value = rule

        r1 = get_active_rule_cached(ttl_sec=60)
        self.assertIs(r1, rule)
        mock_get_active.assert_called_once()
        mock_cache.set.assert_called_once_with("assign_rule_active_v2", rule, 60)

        # call ที่สอง: cache.get -> rule
        mock_get_active.reset_mock()
        mock_cache.get.return_value = rule

        r2 = get_active_rule_cached(ttl_sec=60)
        self.assertIs(r2, rule)
        mock_get_active.assert_not_called()


# -------------------------------------------------------------------
#  AutoDispatcher.__init__ (Dummy rule branch)
# -------------------------------------------------------------------


class TestAutoDispatcherInit(TestCase):
    @patch("tickets.dispatcher.get_active_rule_cached", return_value=None)
    def test_init_uses_dummy_rule_when_no_active_rule(self, mock_get_rule):
        """
        ถ้า get_active_rule_cached คืน None → ต้องสร้าง _Dummy rule
        เพื่อกันไม่ให้ self.rule เป็น None
        """
        d = AutoDispatcher()
        self.assertIsNotNone(d.rule)
        self.assertTrue(hasattr(d.rule, "max_open_tickets"))
        self.assertTrue(hasattr(d.rule, "weight_distance"))
        self.assertTrue(hasattr(d.rule, "weight_workload"))


# -------------------------------------------------------------------
#  AutoDispatcher helpers
# -------------------------------------------------------------------


class TestAutoDispatcherHelpers(TestCase):
    def setUp(self):
        @dataclass
        class DummyRule:
            max_open_tickets: int = MAX_TOTAL_OPEN
            weight_distance: float = 1.0
            weight_workload: float = 2.0

        self.rule = DummyRule()
        self.dispatcher = AutoDispatcher(rule=self.rule)

    def test_has_slot_respects_limits(self):
        """_has_slot ต้องเคารพเพดาน total / pending / inprog"""
        self.assertTrue(self.dispatcher._has_slot({"total": 0, "pending": 0, "inprog": 0}))
        self.assertFalse(self.dispatcher._has_slot({"total": MAX_TOTAL_OPEN, "pending": 0, "inprog": 0}))
        self.assertFalse(self.dispatcher._has_slot({"total": 1, "pending": MAX_PENDING, "inprog": 0}))
        self.assertFalse(self.dispatcher._has_slot({"total": 1, "pending": 0, "inprog": MAX_INPROG}))

    @patch("tickets.dispatcher.Ticket")
    def test_open_counts_buckets_aggregates_by_status(self, MockTicket):
        """
        _open_counts_buckets:
        - รวมงานทุกสถานะ (ยกเว้น DONE)
        - แยกเป็น total / pending / inprog
        - row ที่ assigned_to=None ต้องถูกข้าม (continue)
        """
        rows: List[Dict[str, Any]] = [
            {"assigned_to": 1, "status": "PENDING", "n": 1},
            {"assigned_to": 1, "status": "IN_PROGRESS", "n": 2},
            {"assigned_to": 2, "status": "ASSIGNED", "n": 1},
            {"assigned_to": None, "status": "PENDING", "n": 5},  # ทดสอบ branch continue
        ]
        MockTicket.objects.exclude.return_value.values.return_value.annotate.return_value = rows

        buckets = self.dispatcher._open_counts_buckets()
        # tech 1: total=3, pending=1, inprog=2
        self.assertEqual(buckets[1]["total"], 3)
        self.assertEqual(buckets[1]["pending"], 1)
        self.assertEqual(buckets[1]["inprog"], 2)
        # tech 2: ASSIGNED อยู่ใน PENDING_BUCKET
        self.assertEqual(buckets[2]["total"], 1)
        self.assertEqual(buckets[2]["pending"], 1)
        self.assertEqual(buckets[2]["inprog"], 0)
        # ไม่มี tech_id=None อยู่ใน buckets
        self.assertNotIn(None, buckets)

    @patch("tickets.dispatcher.TechnicianPresence")
    def test_candidate_presences_filters_bbox_and_available(self, MockPresence):
        """
        _candidate_presences:
        - filter เฉพาะ role=technician
        - filter is_available ถ้ามี field นี้
        - filter bbox ตามรัศมี
        """
        qs = MagicMock()
        qs.select_related.return_value = qs
        qs.only.return_value = qs
        qs.filter.return_value = qs

        MockPresence.objects.filter.return_value = qs
        f = MagicMock()
        f.name = "is_available"
        MockPresence._meta.get_fields.return_value = [f]

        ticket = MagicMock()
        ticket.latitude = 13.0
        ticket.longitude = 100.0

        result_qs = self.dispatcher._candidate_presences(ticket, search_radius_km=5.0)

        self.assertIs(result_qs, qs)
        MockPresence.objects.filter.assert_called_once()
        self.assertGreaterEqual(qs.filter.call_count, 2)

    @patch("tickets.dispatcher.Ticket")
    @patch("tickets.dispatcher.bbox_for_radius_km")
    @patch("tickets.dispatcher.haversine_km")
    def test_calculate_priority_score_heatmap_increases_score(
        self, mock_hav, mock_bbox, MockTicket
    ):
        """
        calculate_priority_score:
        - เทียบคะแนนกรณีไม่มี ticket ข้างเคียง vs มี ticket ข้างเคียง
        - กรณีมีเพื่อนบ้านในรัศมี → score ต้องเพิ่มขึ้น
        """
        ticket = MagicMock()
        ticket.id = 1
        ticket.urgency_level = "LOW"
        ticket.category = None
        ticket.latitude = 13.0
        ticket.longitude = 100.0

        # baseline: ไม่มี neighbor เลย
        empty_qs = MagicMock()
        empty_qs.exclude.return_value = empty_qs
        empty_qs.only.return_value = empty_qs
        empty_qs.iterator.return_value = []

        # heatmap: มี neighbor 1 คน ในระยะใกล้ ๆ
        other = MagicMock()
        other.latitude = 13.0
        other.longitude = 100.0

        qs_with = MagicMock()
        qs_with.exclude.return_value = qs_with
        qs_with.only.return_value = qs_with
        qs_with.iterator.return_value = [other]

        # ไม่ให้เข้า branch qs = qs.filter(...) เพื่อจะได้ใช้ iterator ที่เราตั้งไว้
        mock_bbox.return_value = None
        mock_hav.return_value = 0.2  # <= 0.5km → นับเป็น nearby

        # 1) baseline: ไม่มี heatmap
        MockTicket.objects.filter.return_value = empty_qs
        score_no_heatmap = self.dispatcher.calculate_priority_score(ticket)

        # 2) มีเพื่อนบ้าน 1 ตัว
        MockTicket.objects.filter.return_value = qs_with
        score_with_heatmap = self.dispatcher.calculate_priority_score(ticket)

        self.assertGreater(score_with_heatmap, score_no_heatmap)

    def test_calculate_priority_score_default_values(self):
        """กรณีไม่มี urgency/หมวดหมู่/พิกัด → ได้ค่า default"""
        ticket = MagicMock()
        ticket.urgency_level = "UNKNOWN"  # default 0.2
        ticket.category = None
        ticket.latitude = None
        ticket.longitude = None

        score = self.dispatcher.calculate_priority_score(ticket)
        self.assertAlmostEqual(score, 0.2, places=2)

    @patch("tickets.dispatcher.Ticket")
    @patch("tickets.dispatcher.bbox_for_radius_km", return_value=None)
    def test_calculate_priority_skip_invalid_latlon(
        self, mock_bbox, MockTicket
    ):
        """ต้องข้าม ticket เพื่อนบ้านที่ latitude/longitude พัง (ไม่ทำให้ nearby_count เพิ่ม)"""
        ticket = MagicMock()
        ticket.id = 1
        ticket.urgency_level = "LOW"
        ticket.category = None
        ticket.latitude = 10.0
        ticket.longitude = 20.0

        bad_neighbor = MagicMock()
        bad_neighbor.latitude = None      # ทำให้ haversine_km คืน inf
        bad_neighbor.longitude = "ABC"    # แปลง float ไม่ได้

        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.only.return_value = qs
        qs.iterator.return_value = [bad_neighbor]

        MockTicket.objects.filter.return_value = qs

        score = self.dispatcher.calculate_priority_score(ticket)

        # LOW → base=0.0 และ invalid lat/lon → ไม่ถูกนับเป็น nearby → score = 0.0
        self.assertEqual(score, 0.0)


# -------------------------------------------------------------------
#  AutoDispatcher.find_best_technician
# -------------------------------------------------------------------


class TestFindBestTechnician(TestCase):
    def setUp(self):
        @dataclass
        class DummyRule:
            max_open_tickets: int = MAX_TOTAL_OPEN
            weight_distance: float = 1.0
            weight_workload: float = 2.0

        self.rule = DummyRule()
        self.dispatcher = AutoDispatcher(rule=self.rule)

    def _fake_presence(self, tech_id: int, username: str, lat: float, lon: float):
        tech = MagicMock()
        tech.id = tech_id
        tech.username = username
        presence = MagicMock()
        presence.technician_id = tech_id
        presence.technician = tech
        presence.latitude = lat
        presence.longitude = lon
        return presence

    def test_find_best_technician_returns_none_when_no_candidate(self):
        """ไม่มี candidate เลย → ต้องคืน DispatchResult.technician = None"""
        ticket = MagicMock()
        ticket.latitude = 13.0
        ticket.longitude = 100.0

        fake_qs = MagicMock()
        fake_qs.exists.return_value = False
        fake_qs.iterator.return_value = iter([])

        with patch.object(self.dispatcher, "_candidate_presences", return_value=fake_qs):
            result = self.dispatcher.find_best_technician(ticket)

        self.assertIsNone(result.technician)
        self.assertIn("ไม่พบช่างในพื้นที่", result.reason)

    @patch("tickets.dispatcher.haversine_km", return_value=1.0)
    @patch("tickets.dispatcher.fast_distance_km", return_value=1.0)
    def test_find_best_technician_choose_by_workload_then_distance(
        self, mock_fast, mock_hav
    ):
        """
        มี candidate 2 คน:
        - คนแรกมีงานค้างน้อยกว่า → ต้องถูกเลือก แม้ระยะเท่ากัน
        """
        ticket = MagicMock()
        ticket.latitude = 13.0
        ticket.longitude = 100.0

        p1 = self._fake_presence(1, "tech_low_work", 13.0, 100.0)
        p2 = self._fake_presence(2, "tech_high_work", 13.1, 100.1)

        buckets = {
            1: {"total": 0, "pending": 0, "inprog": 0},
            2: {"total": 1, "pending": 0, "inprog": 0},  # ยังไม่ถึงเพดาน
        }

        fake_qs = MagicMock()
        fake_qs.exists.return_value = True
        fake_qs.iterator.return_value = iter([p1, p2])

        with patch.object(self.dispatcher, "_candidate_presences", return_value=fake_qs), \
             patch.object(self.dispatcher, "_open_counts_buckets", return_value=buckets), \
             patch.object(self.dispatcher, "calculate_priority_score", return_value=0.0):
            result = self.dispatcher.find_best_technician(ticket)

        self.assertIsInstance(result, DispatchResult)
        self.assertIsNotNone(result.technician)
        self.assertEqual(result.technician.username, "tech_low_work")
        self.assertEqual(result.open_tickets, 0)
        self.assertIn("เลือก", result.reason)

    @patch("tickets.dispatcher.TechnicianPresence")
    @patch("tickets.dispatcher.haversine_km", return_value=1.0)
    @patch("tickets.dispatcher.fast_distance_km", return_value=1.0)
    def test_find_best_technician_without_location_uses_all_available(
        self, mock_fast, mock_hav, MockPresence
    ):
        """
        กรณี ticket ไม่มี latitude/longitude:
        - ต้องใช้ TechnicianPresence.objects.filter(is_available=True, technician__role='technician')
        """
        ticket = MagicMock()
        ticket.latitude = None
        ticket.longitude = None

        p = self._fake_presence(1, "tech_any", 13.0, 100.0)

        qs = MagicMock()
        qs.select_related.return_value = qs
        qs.iterator.return_value = iter([p])

        MockPresence.objects.filter.return_value = qs

        buckets = {1: {"total": 0, "pending": 0, "inprog": 0}}

        with patch.object(self.dispatcher, "_open_counts_buckets", return_value=buckets):
            result = self.dispatcher.find_best_technician(ticket)

        self.assertIsNotNone(result.technician)
        MockPresence.objects.filter.assert_called_once_with(is_available=True, technician__role="technician")

    def test_find_best_technician_all_full_capacity_returns_no_slot(self):
        """
        ถ้าทุกคนมีงานถึงเพดาน → filtered ว่าง → ต้องคืนข้อความงานถึงเพดาน
        """
        ticket = MagicMock()
        ticket.latitude = 13.0
        ticket.longitude = 100.0

        p1 = self._fake_presence(1, "tech_full", 13.0, 100.0)

        fake_qs = MagicMock()
        fake_qs.exists.return_value = True
        fake_qs.iterator.return_value = iter([p1])

        buckets = {
            1: {"total": MAX_TOTAL_OPEN, "pending": MAX_PENDING, "inprog": MAX_INPROG},
        }

        with patch.object(self.dispatcher, "_candidate_presences", return_value=fake_qs), patch.object(
            self.dispatcher, "_open_counts_buckets", return_value=buckets
        ), patch.object(self.dispatcher, "_has_slot", return_value=False):
            result = self.dispatcher.find_best_technician(ticket)

        self.assertIsNone(result.technician)
        self.assertIn("งานถึงเพดานต่อคน", result.reason)

    @patch("tickets.dispatcher.fast_distance_km", return_value=1.0)
    @patch("tickets.dispatcher.haversine_km")
    def test_find_best_technician_scoring_all_workload_and_distance_branches(
        self, mock_hav, mock_fast
    ):
        """
        ทดสอบ loop คำนวณคะแนน:
        - ให้มี technician 3 คน เพื่อกด branch:
          workload_score = 1.0, 0.5, 0.0
          dist_score = 1.0, 0.5, 0.1
        """
        ticket = MagicMock()
        ticket.latitude = 13.0
        ticket.longitude = 100.0

        p1 = self._fake_presence(1, "tech0", 13.0, 100.0)
        p2 = self._fake_presence(2, "tech1", 13.1, 100.1)
        p3 = self._fake_presence(3, "tech3", 13.2, 100.2)

        # total_open: 0, 1, 3
        buckets = {
            1: {"total": 0, "pending": 0, "inprog": 0},
            2: {"total": 1, "pending": 0, "inprog": 0},
            3: {"total": 3, "pending": 0, "inprog": 0},
        }

        fake_qs = MagicMock()
        fake_qs.exists.return_value = True
        fake_qs.iterator.return_value = iter([p1, p2, p3])

        # ระยะจริง: <=1, <=5, อื่น ๆ
        mock_hav.side_effect = [0.5, 2.0, 10.0]

        with patch.object(self.dispatcher, "_candidate_presences", return_value=fake_qs), \
             patch.object(self.dispatcher, "_open_counts_buckets", return_value=buckets), \
             patch.object(self.dispatcher, "calculate_priority_score", return_value=0.0), \
             patch.object(self.dispatcher, "_has_slot", return_value=True):
            result = self.dispatcher.find_best_technician(ticket)

        # แค่ยืนยันว่าเลือก technician คนใดคนหนึ่งได้ และ loop ทำงานครบทุก branch
        self.assertIsInstance(result, DispatchResult)
        self.assertIsNotNone(result.technician)

    def test_find_best_technician_reservation_mode(self):
        """โหมด reservation (แม้ตอนนี้โค้ดไม่ใช้ mode) ก็ต้องหา technician ได้ปกติ"""
        self.dispatcher.mode = "reservation"  # แค่ตั้งค่า attribute เพิ่ม

        ticket = MagicMock()
        ticket.latitude = 10
        ticket.longitude = 20
        ticket.id = 1  # ป้องกันปัญหาเวลาเอาไปใช้ในที่อื่น

        p = self._fake_presence(1, "tech1", 10, 20)

        fake_qs = MagicMock()
        fake_qs.exists.return_value = True
        fake_qs.iterator.return_value = iter([p])

        with patch.object(self.dispatcher, "_candidate_presences", return_value=fake_qs), \
             patch.object(self.dispatcher, "_open_counts_buckets", return_value={1: {"total": 0, "pending": 0, "inprog": 0}}), \
             patch.object(self.dispatcher, "calculate_priority_score", return_value=0.0):

            result = self.dispatcher.find_best_technician(ticket)

        self.assertIsNotNone(result.technician)
        self.assertEqual(result.technician.username, "tech1")



# -------------------------------------------------------------------
#  AutoDispatcher.dispatch & auto_dispatch_ticket
# -------------------------------------------------------------------


class TestDispatchProcess(TestCase):
    def setUp(self):
        @dataclass
        class DummyRule:
            max_open_tickets: int = MAX_TOTAL_OPEN
            weight_distance: float = 1.0
            weight_workload: float = 2.0

        self.rule = DummyRule()

    @patch("tickets.dispatcher.notify_ticket_assigned")
    @patch("tickets.dispatcher.TicketStatusHistory")
    @patch("tickets.dispatcher.Ticket")
    def test_dispatch_assigns_and_logs_history(
        self, MockTicket, MockHistory, mock_notify
    ):
        """
        dispatch():
        - ต้อง select_for_update ticket
        - เลือก technician แล้วอัปเดต assigned_to
        - สร้าง TicketStatusHistory
        - เรียก notify_ticket_assigned
        """
        ticket_obj = MagicMock()
        ticket_obj.pk = 1
        ticket_obj.id = 1
        ticket_obj.status = "PENDING"
        ticket_obj.assigned_to = None

        MockTicket.objects.select_for_update.return_value.select_related.return_value.get.return_value = (
            ticket_obj
        )

        technician = MagicMock()
        technician.id = 99
        technician.username = "tech1"

        result = DispatchResult(
            technician=technician,
            reason="เลือก tech1",
            distance_km=1.0,
            score=2.0,
            open_tickets=0,
        )

        dispatcher_obj = AutoDispatcher(rule=self.rule)

        with patch.object(dispatcher_obj, "find_best_technician", return_value=result):
            dispatch_result = dispatcher_obj.dispatch(ticket_obj)

        self.assertIs(ticket_obj.assigned_to, technician)
        ticket_obj.save.assert_called_once_with(update_fields=["assigned_to"])

        MockHistory.objects.create.assert_called_once()
        kwargs = MockHistory.objects.create.call_args.kwargs
        self.assertIs(kwargs["ticket"], ticket_obj)
        self.assertEqual(kwargs["status"], "PENDING")
        self.assertIn("Auto-dispatch", kwargs["note"])

        mock_notify.assert_called_once_with(ticket_obj, technician)

        self.assertIs(dispatch_result.technician, technician)
        self.assertEqual(dispatch_result.reason, "เลือก tech1")

    @patch("tickets.dispatcher.TicketStatusHistory")
    @patch("tickets.dispatcher.Ticket")
    def test_dispatch_no_technician_does_not_change_ticket(
        self, MockTicket, MockHistory
    ):
        """
        dispatch() กรณีไม่มีช่าง:
        - ไม่ควรเปลี่ยน assigned_to
        - ไม่สร้าง TicketStatusHistory
        """
        ticket_obj = MagicMock()
        ticket_obj.pk = 1
        ticket_obj.id = 1
        ticket_obj.status = "PENDING"
        ticket_obj.assigned_to = None

        MockTicket.objects.select_for_update.return_value.select_related.return_value.get.return_value = (
            ticket_obj
        )

        dispatcher_obj = AutoDispatcher(rule=self.rule)

        result = DispatchResult(
            technician=None,
            reason="ไม่พบช่างในพื้นที่",
            distance_km=None,
            score=None,
            open_tickets=None,
        )

        with patch.object(dispatcher_obj, "find_best_technician", return_value=result):
            dispatch_result = dispatcher_obj.dispatch(ticket_obj)

        self.assertIsNone(ticket_obj.assigned_to)
        ticket_obj.save.assert_not_called()
        MockHistory.objects.create.assert_not_called()
        self.assertIsNone(dispatch_result.technician)
        self.assertIn("ไม่พบช่าง", dispatch_result.reason)

    @patch.object(dispatcher.AutoDispatcher, "dispatch")
    def test_auto_dispatch_ticket_wrapper(self, mock_dispatch):
        """auto_dispatch_ticket เป็น wrapper ที่ต้องเรียก AutoDispatcher.dispatch"""
        ticket_obj = MagicMock()
        result = DispatchResult(
            technician=MagicMock(),
            reason="OK",
            distance_km=1.0,
            score=1.0,
            open_tickets=0,
        )
        mock_dispatch.return_value = result

        res = auto_dispatch_ticket(ticket_obj)
        mock_dispatch.assert_called_once()
        self.assertIs(res, result)

class TestExtraCoverage(TestCase):
    def test_calculate_priority_no_latlon_returns_default(self):
        """ไม่มี lat/lon แต่ไม่มี urgency/หมวดหมู่ → ได้ base score 0.2 (ไม่มี heatmap)"""
        ticket = MagicMock()
        ticket.latitude = None
        ticket.longitude = None
        ticket.id = 1
        # ไม่กำหนด urgency_level / category → ใช้ default ภายในฟังก์ชัน

        dispatcher = AutoDispatcher()
        score = dispatcher.calculate_priority_score(ticket)

        # ตามโค้ด: default urgency = 0.2, category = 0.0, heatmap = 0.0
        self.assertEqual(score, 0.2)

    def test_fast_distance_returns_inf_when_any_none(self):
        """fast_distance_km คืน inf ถ้า input มี None"""
        # ใช้ฟังก์ชันระดับ module ที่ import มาแล้วด้านบน
        dist = fast_distance_km(10.0, None, 20.0, 30.0)
        self.assertEqual(dist, float("inf"))

