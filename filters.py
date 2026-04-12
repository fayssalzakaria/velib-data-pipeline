import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    filtre_type: str,
    filtre_etat: str,
    filtre_min_velos: int,
) -> pd.DataFrame:
    df_filtered = df.copy()

    if filtre_type == "Mecaniques uniquement":
        df_filtered = df_filtered[df_filtered["mechanical"] > 0]
    elif filtre_type == "Electriques uniquement":
        df_filtered = df_filtered[df_filtered["ebike"] > 0]

    if filtre_etat == "Vides":
        df_filtered = df_filtered[df_filtered["is_empty"]]
    elif filtre_etat == "Pleines":
        df_filtered = df_filtered[df_filtered["is_full"]]
    elif filtre_etat == "Disponibles":
        df_filtered = df_filtered[
            (~df_filtered["is_empty"]) & (~df_filtered["is_full"])
        ]

    df_filtered = df_filtered[df_filtered["numbikesavailable"] >= filtre_min_velos]

    return df_filtered