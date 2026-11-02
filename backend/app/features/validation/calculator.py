def calculate_total(
    four_hand: int, five_hand: int, six_hand: int, eight_hand: int, cluster: int
) -> int:
    """Total Quantity = Four-Hand + Five-Hand + Six-Hand + Eight-Hand + Cluster, per spec."""
    return four_hand + five_hand + six_hand + eight_hand + cluster
