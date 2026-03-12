from pydantic import BaseModel


class OverviewMetrics(BaseModel):
    revenue_ytd: float
    avg_ticket: float
    total_clients: int
    active_clients: int
    inactive_clients: int
    new_clients_90: int
    service_mix_label: str
    service_mix_percent: int
    color_coverage_percent: int
    photo_coverage_percent: int
