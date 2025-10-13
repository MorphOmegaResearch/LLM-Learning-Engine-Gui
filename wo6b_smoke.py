from Data import config as C

# simulate two variants for the same base
base = "Qwen2.5-0.5b-Instruct"
for v, t in [("Qwen2.5-0.5b_coder","coder"), ("Qwen2.5-0.5b_researcher","researcher")]:
    C.save_model_profile(v, {"trainee_name": v, "base_model": base, "assigned_type": t})
    try:
        C.upsert_training_profile_for_model(v, base, t)
    except TypeError:
        C.upsert_training_profile_for_model(v)

items = C.list_model_profiles()
print("profiles:", [ (i.get("variant_id"), i.get("assigned_type")) for i in items ])
assert any(i.get("variant_id")=="Qwen2.5-0.5b_coder" for i in items)
assert any(i.get("variant_id")=="Qwen2.5-0.5b_researcher" for i in items)
print("OK: WO-6b smoke passed")