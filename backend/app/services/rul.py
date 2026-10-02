BASE_FADE_PCT_PER_YEAR = 1.8

EOL_THRESHOLD_PCT = 70.0


def project(
    vehicle_id: str,
    current_soh: float,
    cycles: int,
    start_year: int = 2026,
    years: int = 5
):

    stress = min(
        1.6,
        1.0 + cycles / 2000
    )

    fade = round(
        BASE_FADE_PCT_PER_YEAR * stress,
        2
    )

    if fade > 0:

        rul_years = round(
            max(
                0.0,
                current_soh - EOL_THRESHOLD_PCT
            )
            / fade,
            1
        )

    else:

        rul_years = 0.0

    projection = []

    soh = current_soh

    for i in range(years):

        soh = round(
            max(
                0.0,
                soh - fade
            ),
            1
        )

        projection.append(
            {
                "year": start_year + i,
                "soh": soh
            }
        )

    return {

        "vehicle_id": vehicle_id,

        "current_soh": current_soh,

        "degradation_pct_per_year": fade,

        "rul_years": rul_years,

        "projection": projection
    }