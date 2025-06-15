# Typesense document schemas.
REFERRALS_SCHEMA = {
    "name": "referrals",
    "fields": [
        {"name": "created", "type": "float"},
        {"name": "type", "type": "string", "facet": True},
        {"name": "referring_org", "type": "string", "facet": True},
        {"name": "regions", "type": "string[]", "facet": True},
        {"name": "reference", "type": "string"},
        {"name": "description", "type": "string"},
        {"name": "address", "type": "string"},
        {"name": "point", "type": "geopoint", "optional": True},
        {"name": "lga", "type": "string", "facet": True},
        {"name": "dop_triggers", "type": "string[]", "facet": True},
    ],
}
# client.collections.create(REFERRALS_SCHEMA)

RECORDS_SCHEMA = {
    "name": "records",
    "fields": [
        {"name": "created", "type": "float"},
        {"name": "referral_id", "type": "int32"},
        {"name": "name", "type": "string"},
        {"name": "description", "type": "string", "optional": True},
        {"name": "file_name", "type": "string", "optional": True},
        {"name": "file_type", "type": "string", "facet": True, "optional": True},
        {"name": "file_content", "type": "string", "optional": True},
    ],
}
# client.collections.create(RECORDS_SCHEMA)

NOTES_SCHEMA = {
    "name": "notes",
    "fields": [
        {"name": "created", "type": "float"},
        {"name": "referral_id", "type": "int32"},
        {"name": "note", "type": "string"},
    ],
}
# client.collections.create(NOTES_SCHEMA)

TASKS_SCHEMA = {
    "name": "tasks",
    "fields": [
        {"name": "created", "type": "float"},
        {"name": "referral_id", "type": "int32"},
        {"name": "description", "type": "string", "optional": True},
        {"name": "assigned_user", "type": "string"},
    ],
}
# client.collections.create(TASKS_SCHEMA)

CONDITIONS_SCHEMA = {
    "name": "conditions",
    "fields": [
        {"name": "created", "type": "float"},
        {"name": "referral_id", "type": "int32"},
        {"name": "proposed_condition", "type": "string", "optional": True},
        {"name": "approved_condition", "type": "string", "optional": True},
    ],
}
# client.collections.create(CONDITIONS_SCHEMA)
