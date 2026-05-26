"""
Views package — each module exposes a render() function.

Shared state contract (st.session_state keys):
  "search_query"    str   — current search term (set by main app)
  "search_results"  list  — raw results returned by the API pipeline
  "selected_record" dict  — single record the user clicked/highlighted
  "pinned_records"  list  — records explicitly pinned for comparison
"""
