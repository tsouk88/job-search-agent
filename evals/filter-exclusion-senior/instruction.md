Search remote job listings and apply the user's exclusions.

Return every listing that matches the query, minus the ones the user does not
want. A seniority term excludes a listing only when it appears in the job
title; any other term excludes a listing when it appears anywhere in the
listing.

```json
{"query": "python developer", "exclude": ["senior", "game", "canonical"]}
```

Write the resulting listings to `/app/output.json` as a JSON list.
