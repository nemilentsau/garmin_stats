# Backlog

This file tracks active parked work only. Completed implementation notes belong
in the code, tests, or current architecture docs.

## 1. Add Daily Check-In UI On `/today`

See [checkin-todo.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/checkin-todo.md).

Reason:

- backend check-in support already exists
- assistant and experiment analysis both benefit from subjective context
- there is currently no frontend entry surface

Recommended shape:

- compact `Daily Check-In` card on `/today`
- today-first entry flow
- preserve the existing `/api/checkins` contract
