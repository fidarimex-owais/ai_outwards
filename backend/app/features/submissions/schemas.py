from pydantic import BaseModel


class SubmissionOut(BaseModel):
    session_id: str
    company_name: str
    vehicle_number: str
    container_number: str
    brand: str
    line_supervisor_name: str
    weight: float
    four_hand: int
    five_hand: int
    six_hand: int
    eight_hand: int
    cluster: int
    total: int
    labor_name: str
    driver_name: str
    cold_storage_name: str
    cold_storage_supervisor_name: str
    vehicle_in_time: str
    vehicle_out_time: str
    unloading_time: str
    saved_at: str


class CorrectionRequest(BaseModel):
    text: str  # free-form spoken correction; which field it refers to is detected server-side
