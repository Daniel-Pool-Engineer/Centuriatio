from backend.agent.agent import RoleProfile

# One profile per role; fields are consumed by VillagerAgent.build_prompt().
CITIZEN = RoleProfile(
    role="citizen",
    workplace="office",
    suggested_actions={
        "work", "shop", "check_supplies", "conserve", "seek_help",
        "return_home", "stay", "travel",
    },
    identity_line="You are a citizen of the village.",
    role_guidance=(
        "During normal days you work, shop, and return home at night."
        "During an outage, check supplies, conserve, seek help only in daylight, "
        "and stay home after dark."
    ),
    speed=1.0,
)

FIRST_RESPONDER = RoleProfile(
    role="first_responder",
    workplace="fire",
    suggested_actions={
        "work", "shop", "patrol", "assist_residents", "check_for_help_needed", 
        "return_home", "stay", "travel"
    },
    identity_line="You are a first responder (firefighter) of the village.",
    role_guidance=(
        "During normal days you work at the police station. "
        "During an outage, you must patrol DIFFERENT areas of the map "
        "(e.g., hospital, home_a, home_b, home_c, home_d, grocery, electrical). "
        "Do not stay in one place. Check for help needed and assist residents."
    ),
    speed=1.0
)

ELECTRICIAN = RoleProfile(
    role = "electrician",
    workplace="electrical",
    suggested_actions={
        "work", "shop", "check_supplies", "order_supplies", "inspect", "maintain_safe_area", 
        "restore_power", "return_home", "stay", "travel", "test"
    },
    identity_line="You are an electrician of the village.",
    role_guidance=(
        "During normal days you work, shop, and return home at night. "
        "During an outage day, inspect electrical failures at the electrical plant, "
        "identify required repairs, "
        "order necessary components and check the status of replacement parts. "
        "Maintain a safe repair area, "
        "restore power when the required equipment becomes available, indicated by the 'arrived' status."
    ),
    speed = 1.0
)

DOCTOR = RoleProfile(
    role="doctor",
    workplace="hospital",
    suggested_actions={
        "work", "check_backup", "protect_medication", "conserve", 
        "request_resources", "return_home", "stay", "travel"
    },
    identity_line="You are the doctor of the village hospital.",
    role_guidance=(
        "During normal days you work at the hospital and return home at night. "
        "During an outage, check the hospital backup power, protect medication, "
        "reduce non-essential use, and monitor patients. Request resources if needed."
    ),
    speed=1.0
)
