import traceback


def run():
    from hmd_agro.hmd_agro.tests.seed_data import seed
    try:
        result = seed()
        print("SUCCESS:", result)
    except Exception:
        traceback.print_exc()
