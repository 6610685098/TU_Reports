# tickets/dispatcher.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from math import radians, sin, cos, asin, sqrt, pi
from typing import Optional, Tuple, List, Dict

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    Ticket,
    TechnicianPresence,
    AssignmentRule,
    TicketStatusHistory,
)
from authentication.models import User

# พยายาม import notify ถ้าไม่มี ให้ทำเป็น no-op
try:
    from notify.utils import notify_ticket_assigned  # type: ignore
except Exception:  # pragma: no cover
    def notify_ticket_assigned(*args, **kwargs):
        return None

logger = logging.getLogger(__name__)

# =============================================================================
# ค่าคงที่/ยูทิล
# =============================================================================

EARTH_RADIUS_KM = 6371.0088  # WGS84

# กำหนดบัคเก็ตสถานะ
PENDING_BUCKET = {"PENDING", "ASSIGNED"}          # รอดำเนินการ
INPROG_BUCKET = {"IN_PROGRESS"}                   # กำลังทำ
DONE_BUCKET    = {"COMPLETED", "CLOSED", "REJECTED"}  # ปิดงาน

# ข้อจำกัดต่อคน: รวม ≤2 งาน และไม่เกิน 1 งานต่อบัคเก็ต
MAX_TOTAL_OPEN = 2
MAX_PENDING    = 1
MAX_INPROG     = 1

def _to_float(x) -> Optional[float]:
    """แปลงค่าใด ๆ เป็น float (รองรับ Decimal/str/None)"""
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    lat1 = _to_float(lat1); lon1 = _to_float(lon1)
    lat2 = _to_float(lat2); lon2 = _to_float(lon2)
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    φ1, λ1, φ2, λ2 = map(radians, (lat1, lon1, lat2, lon2))
    dφ, dλ = φ2 - φ1, λ2 - λ1
    a = sin(dφ / 2) ** 2 + cos(φ1) * cos(φ2) * sin(dλ / 2) ** 2
    return 2.0 * EARTH_RADIUS_KM * asin(sqrt(a))

def fast_distance_km(lat1, lon1, lat2, lon2) -> float:
    lat1 = _to_float(lat1); lon1 = _to_float(lon1)
    lat2 = _to_float(lat2); lon2 = _to_float(lon2)
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    x = radians(lon2 - lon1) * cos(radians((lat1 + lat2) / 2.0))
    y = radians(lat2 - lat1)
    return EARTH_RADIUS_KM * (x * x + y * y) ** 0.5

def bbox_for_radius_km(lat, lon, km: float) -> Optional[Tuple[float, float, float, float]]:
    lat = _to_float(lat); lon = _to_float(lon)
    if None in (lat, lon):
        return None
    # โดยประมาณ: 1°lat ≈ 111km, 1°lon ≈ 111km*cos(lat)
    dlat = km / 111.0
    denom = max(0.2, abs(cos(radians(lat))))  # กัน division เล็กมากใกล้ขั้วโลก
    dlon = km / (111.0 * denom)
    return (lat - dlat, lat + dlat, lon - dlon, lon + dlon)

def get_active_rule_cached(ttl_sec: int = 60) -> AssignmentRule:
    key = "assign_rule_active_v2"
    rule = cache.get(key)
    if rule is None:
        rule = AssignmentRule.get_active_or_default()
        cache.set(key, rule, ttl_sec)
    return rule

# =============================================================================
# Result type
# =============================================================================

@dataclass
class DispatchResult:
    technician: Optional[User]
    reason: str
    distance_km: Optional[float] = None
    score: Optional[float] = None
    open_tickets: Optional[int] = None

# =============================================================================
# Core
# =============================================================================

class AutoDispatcher:
    """
    ตัวมอบหมาย Ticket อัตโนมัติ (ไม่ใช้ GeoDjango)
    - กรองจาก TechnicanPresence แบบ is_available + bbox
    - บังคับเพดานงาน: รวม ≤2 และบัคเก็ตละ ≤1 (pending / in-progress)
    - จัดอันดับ: งานค้างน้อย → ระยะใกล้ → คะแนนพิเศษเล็กน้อย
    - ใช้ transaction + select_for_update กันชนกัน
    """

    def __init__(self, rule: Optional[AssignmentRule] = None) -> None:
        self.rule: AssignmentRule = rule or get_active_rule_cached()
        if not self.rule:  # กัน null
            class _Dummy:
                max_open_tickets = MAX_TOTAL_OPEN
                weight_distance = 1.0
                weight_workload = 2.0
            self.rule = _Dummy()  # type: ignore

    # ------------ Priority (เล็กน้อย เพิ่มน้ำหนักความเร่งด่วน + heatmap) ------------
    def calculate_priority_score(self, ticket: Ticket) -> float:
        score = 0.0

        urgency_weights = {"LOW": 0.0, "MEDIUM": 0.2, "HIGH": 0.4, "CRITICAL": 0.6}
        score += urgency_weights.get(getattr(ticket, "urgency_level", None), 0.2)

        cat_name = getattr(getattr(ticket, "category", None), "name", None)
        cat_w = {"ไฟฟ้า": 0.2, "ประปา": 0.2, "แอร์/ระบายอากาศ": 0.1}.get(cat_name, 0.0)
        score += cat_w

        # ความหนาแน่นใน 500m / 30 วันล่าสุด
        nearby_count = 0
        if ticket.latitude is not None and ticket.longitude is not None:
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            qs = (
                Ticket.objects.filter(created_at__gte=thirty_days_ago)
                .exclude(id=ticket.id)
                .only("id", "latitude", "longitude")
            )
            bbox = bbox_for_radius_km(ticket.latitude, ticket.longitude, km=1.0)
            if bbox:
                min_lat, max_lat, min_lon, max_lon = bbox
                qs = qs.filter(
                    latitude__gte=min_lat, latitude__lte=max_lat,
                    longitude__gte=min_lon, longitude__lte=max_lon
                )
            for t in qs.iterator(chunk_size=500):
                if haversine_km(ticket.latitude, ticket.longitude, t.latitude, t.longitude) <= 0.5:
                    nearby_count += 1

        score += min(nearby_count * 0.05, 0.3)
        return round(score, 2)

    # -------------------------- Helpers: workload/buckets --------------------------
    def _open_counts_buckets(self) -> Dict[int, Dict[str, int]]:
        """
        นับงานเปิดของทุก technician และแตกเป็นบัคเก็ต:
        { tech_id: { 'total': n_all, 'pending': n_pending, 'inprog': n_inprog } }
        """
        rows = (
            Ticket.objects.exclude(status__in=DONE_BUCKET)
            .values("assigned_to", "status")
            .annotate(n=Count("id"))
        )
        per_tech: Dict[int, Dict[str, int]] = {}
        for r in rows:
            tech_id = r["assigned_to"]
            if tech_id is None:
                continue
            st = r["status"]
            per_tech.setdefault(tech_id, {"total": 0, "pending": 0, "inprog": 0})
            per_tech[tech_id]["total"] += r["n"]
            if st in PENDING_BUCKET:
                per_tech[tech_id]["pending"] += r["n"]
            elif st in INPROG_BUCKET:
                per_tech[tech_id]["inprog"] += r["n"]
        return per_tech

    def _has_slot(self, bucket: Dict[str, int]) -> bool:
        """
        มีช่องว่างตามเกณฑ์ไหม:
          - รวม < 2
          - pending < 1
          - inprog < 1
        """
        return (
            bucket.get("total", 0) < MAX_TOTAL_OPEN
            and bucket.get("pending", 0) < MAX_PENDING
            and bucket.get("inprog", 0) < MAX_INPROG
        )

    # ------------------------- Candidate presences (bbox) -------------------------
    def _candidate_presences(self, ticket: Ticket, search_radius_km: float = 20.0):
        presences = TechnicianPresence.objects.filter(
            technician__role="technician",
            technician__is_active=True,
        ).select_related("technician").only(
            "id", "technician_id", "latitude", "longitude", "is_available",
            "technician__id", "technician__username", "technician__first_name", "technician__last_name"
        )

        if "is_available" in {f.name for f in TechnicianPresence._meta.get_fields()}:
            presences = presences.filter(is_available=True)

        bbox = bbox_for_radius_km(ticket.latitude, ticket.longitude, km=search_radius_km)
        if bbox:
            min_lat, max_lat, min_lon, max_lon = bbox
            presences = presences.filter(
                latitude__gte=min_lat, latitude__lte=max_lat,
                longitude__gte=min_lon, longitude__lte=max_lon
            )
        return presences

    # ------------------------------- Scoring/selection ----------------------------
    def find_best_technician(self, ticket: Ticket) -> DispatchResult:
        weight_dist = float(getattr(self.rule, "weight_distance", 1.0))
        weight_work = float(getattr(self.rule, "weight_workload", 2.0))
        

        # 1) หา candidate ในรัศมี 20 → 40 → 80 กม. และ fallback ถ้าไม่มีพิกัด
        candidates = None
        if ticket.latitude is not None and ticket.longitude is not None:
            for radius in (20.0, 40.0, 80.0):
                qs = self._candidate_presences(ticket, search_radius_km=radius)
                if qs.exists():
                    candidates = list(qs.iterator(chunk_size=500))
                    break
        else:
            # ไม่มีพิกัด → เอาช่างว่างทั้งหมด
            candidates = list(
                TechnicianPresence.objects.filter(is_available=True, technician__role="technician")
                .select_related("technician").iterator(chunk_size=500)
            )

        if not candidates:
            return DispatchResult(None, "ไม่พบช่างในพื้นที่ที่พร้อมรับงาน")

        # 2) นับงานค้างแบบบัคเก็ตครั้งเดียว
        buckets = self._open_counts_buckets()

        # 3) กรองตามเพดาน (≤2 รวม, ≤1/บัคเก็ต)
        filtered: List[TechnicianPresence] = []
        for p in candidates:
            b = buckets.get(p.technician_id, {"total": 0, "pending": 0, "inprog": 0})
            if self._has_slot(b):
                filtered.append(p)

        if not filtered:
            return DispatchResult(None, "ไม่พบช่างที่พร้อมรับงาน (งานถึงเพดานต่อคน)")

        # 4) จัดอันดับ: งานค้างน้อย → ระยะใกล้ → คะแนนพิเศษ
        prelim = []
        for p in filtered:
            # โหลดงาน
            b = buckets.get(p.technician_id, {"total": 0, "pending": 0, "inprog": 0})
            total_open = b.get("total", 0)

            # ระยะทาง (เร็ว)
            d_fast = fast_distance_km(ticket.latitude, ticket.longitude, p.latitude, p.longitude)

            prelim.append((total_open, d_fast, p))

        prelim.sort(key=lambda x: (x[0], x[1]))
        prelim = prelim[:50]

        # 5) คะแนนละเอียดด้วย haversine + priority
        priority = self.calculate_priority_score(ticket)
        scored = []
        for total_open, d_fast, p in prelim:
            d_true = haversine_km(ticket.latitude, ticket.longitude, p.latitude, p.longitude)
            # น้ำหนัก: งานค้างน้อยดีกว่า → ให้แปลงเป็น "workload_score" สูงเมื่องานน้อย
            # เช่น total=0 → 1.0, total=1 → 0.5, total>=2 → 0
            if total_open == 0:
                workload_score = 1.0
            elif total_open == 1:
                workload_score = 0.5
            else:
                workload_score = 0.0

            # ระยะใกล้ดีกว่า
            if d_true <= 1:
                dist_score = 1.0
            elif d_true <= 5:
                dist_score = 0.5
            else:
                dist_score = 0.1 if d_true != float("inf") else 0.0

            score = workload_score * weight_work + dist_score * weight_dist + priority * 0.1

            scored.append(
                dict(
                    presence=p,
                    technician=p.technician,
                    distance_km=d_true,
                    open_tickets=total_open,
                    score=score,
                )
            )

        if not scored:
            return DispatchResult(None, "ไม่สามารถคำนวณคะแนนผู้สมัครได้")

        best = max(scored, key=lambda x: x["score"])
        tech = best["technician"]
        dist_str = f"{best['distance_km']:.1f}km" if best["distance_km"] != float("inf") else "N/A"
        display_name = getattr(tech, "get_display_name", None)
        display_name = display_name() if callable(display_name) else getattr(tech, "username", "technician")

        reason = (
            f"เลือก {display_name} (งานเปิด={best['open_tickets']}, ระยะ≈{dist_str}, คะแนน={best['score']:.2f})"
        )
        return DispatchResult(
            technician=tech,
            reason=reason,
            distance_km=best["distance_km"],
            score=best["score"],
            open_tickets=best["open_tickets"],
        )

    # ------------------------------- Public API -----------------------------------
    @transaction.atomic
    def dispatch(self, ticket: Ticket) -> DispatchResult:
        """
        มอบหมายช่างให้ ticket (atomic + lock แถว ticket กัน race)
        - เลือกช่าง
        - ถ้าพบ → อัปเดต assigned_to และสร้าง StatusHistory
        - ถ้าไม่พบ → คืนผลด้วยเหตุผล (ไม่แก้สถานะตั๋ว)
        """
        # ล็อกแถว ticket
        ticket = Ticket.objects.select_for_update().select_related(
            "assigned_to", "category"
        ).select_for_update(of=('self',)).get(pk=ticket.pk)

        result = self.find_best_technician(ticket)
        if not result.technician:
            logger.info("[AutoDispatch] failed: %s", result.reason)
            # ไม่เปลี่ยนสถานะตั๋ว แค่แจ้งเหตุผลกลับไปให้ view แสดง
            return result

        technician = result.technician

        # อัปเดต ticket
        ticket.assigned_to = technician
        ticket.save(update_fields=["assigned_to"])

        # บันทึกประวัติ (ใช้สถานะปัจจุบัน ถ้ามี; ถ้าไม่มี ให้ถือว่า 'ASSIGNED')
        status_to_log = getattr(ticket, "status", None) or "ASSIGNED"
        TicketStatusHistory.objects.create(
            ticket=ticket,
            status=status_to_log,
            note=f"Auto-dispatch: {result.reason}",
            changed_by=None,
        )

        # แจ้งเตือน (ไม่ให้ล้มงานหลัก)
        try:
            notify_ticket_assigned(ticket, technician)
        except Exception as e:  # pragma: no cover
            logger.warning("[AutoDispatch] notify failed: ticket=%s tech=%s err=%s", ticket.id, technician.id, e)

        logger.info("[AutoDispatch] OK: ticket=%s -> tech=%s (%s)", ticket.id, technician.id, result.reason)
        return result


# ฟังก์ชันเรียกง่ายจาก view/task
def auto_dispatch_ticket(ticket: Ticket) -> DispatchResult:
    return AutoDispatcher().dispatch(ticket)
