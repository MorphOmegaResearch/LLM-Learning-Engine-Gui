from Data import config as C

name = "WO6_Smoke_Coder"
base = "Qwen2.5-0.5b-Instruct"

# Simulate Types selection persisted to Model Profile
mp = {"trainee_name": name, "base_model": base, "assigned_type": "coder"}
C.save_model_profile(name, mp)

# Build/upsert training profile from type
try:
    C.upsert_training_profile_for_model(name, base, "coder")
except TypeError:
    # Fallback to signature (name only) if previous helper is used
    C.upsert_training_profile_for_model(name)

tp = C.load_training_profile(name) or {}
print("== TRAINING PROFILE ==")
print("assigned_type:", tp.get("assigned_type"))
print("base_model:", tp.get("base_model"))
print("#scripts:", len(tp.get("selected_scripts", [])))
print("#prompts:", len(tp.get("selected_prompts", [])))
print("#schemas:", len(tp.get("selected_schemas", [])))
print("runner.max_time_min:", (tp.get("runner_settings", {}) or {}).get("max_time_min"))

assert tp.get("assigned_type") in ("coder", ["coder"])
assert base in (tp.get("base_model") or "")
assert len(tp.get("selected_scripts", [])) >= 1
print("OK: WO-6 bridge smoke passed")
