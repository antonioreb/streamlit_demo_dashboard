
def optimization_flags(df, min_spend=25):
    flags = []
    for _, r in df.iterrows():
        if r.cost > min_spend and r.orders == 0:
            flags.append("NEGATIVE")
        elif r.roas > 3 and r.campaign_type == "Auto":
            flags.append("PROMOTE")
        else:
            flags.append("OK")
    df["flag"] = flags
    return df
