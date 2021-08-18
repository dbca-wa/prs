# Typesense document schemas.
REFERRALS_SCHEMA = {
    'name': 'referrals',
    'fields': [
        {'name': 'referral_id', 'type': 'int32'},
        {'name': 'type', 'type': 'string', 'facet': True},
        {'name': 'referring_org', 'type': 'string', 'facet': True},
        {'name': 'referral_year', 'type': 'int32', 'facet': True},
        {'name': 'regions', 'type': 'string[]', 'facet': True},
        {'name': 'reference', 'type': 'string'},
        {'name': 'description', 'type': 'string'},
        {'name': 'address', 'type': 'string'},
        {'name': 'point', 'type': 'geopoint', 'optional': True},
        {'name': 'lga', 'type': 'string', 'facet': True},
        {'name': 'dop_triggers', 'type': 'string[]', 'facet': True},
        {'name': 'url', 'type': 'string'},
    ],
    'default_sorting_field': 'referral_id'
}
# client.collections.create(REFERRALS_SCHEMA)

RECORDS_SCHEMA = {
    'name': 'records',
    'fields': [
        {'name': 'record_id', 'type': 'int32'},
        {'name': 'referral_id', 'type': 'int32'},
        {'name': 'name', 'type': 'string'},
        {'name': 'description', 'type': 'string', 'optional': True},
        {'name': 'file_name', 'type': 'string', 'optional': True},
        {'name': 'file_type', 'type': 'string', 'facet': True, 'optional': True},
        {'name': 'file_content', 'type': 'string', 'optional': True},
        {'name': 'url', 'type': 'string'},
    ],
    'default_sorting_field': 'record_id'
}
# client.collections.create(RECORDS_SCHEMA)
