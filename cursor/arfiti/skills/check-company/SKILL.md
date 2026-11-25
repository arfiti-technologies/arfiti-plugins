---
name: check-company
description: Confirm the connected Arfiti company, legal entity and accounting currency before answering a finance question in Cursor.
---

Use the connected Arfiti MCP tools to read the current organization and accessible legal entities. Use the returned entity names and currencies in the answer. If several entities match, ask which one the user means. If no entity exists, report that setup is needed.

If the connector is unavailable, give the user the Arfiti connection guide at https://arfiti.com/docs/getting-started and wait for sign-in. Keep this check read-only. Do not create an entity or change accounting records as part of checking the connection.
