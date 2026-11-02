from pydantic import BaseModel


class SubmissionOut(BaseModel):
    session_id: str
    company_name: str
    vehicle_number: str
    brand: str
    line_mark: str
    weight: float
    four_hand: int
    five_hand: int
    six_hand: int
    eight_hand: int
    cluster: int
    total: int
    remarks: str
    labor_name: str
    vehicle_out_time: str
    vehicle_in_time: str
    vehicle_for_storage: str
    vehicle_receiver_name: str
    saved_at: str


class CorrectionRequest(BaseModel):
    text: str  # free-form spoken correction; which field it refers to is detected server-side
