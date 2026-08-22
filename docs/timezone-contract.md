# Timezone contract

- Store normalized timestamps as timezone-aware UTC values.
- Display user-facing times in `America/New_York`.
- Preserve every source's original timezone or offset in `original_timezone`.
- Reject naive timestamps at fixture and adapter validation boundaries.
