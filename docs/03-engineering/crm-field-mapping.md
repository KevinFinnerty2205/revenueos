# CRM field and stage mapping guide

Admins choose a compatible HubSpot property; RevenueOS never accepts an expression
or arbitrary write property at execution time.

| RevenueOS field | Compatible provider type | Extra rule |
| --- | --- | --- |
| stage | enumeration | explicit pipeline/stage mapping required |
| status | enumeration | intended for an explicitly chosen compatible status property |
| expected close date | date or datetime | exact calendar value; current provider value is previewed |
| estimated value | number | decimal string; currency must match |
| next step | string | prepared from final Next Best Action where available |
| description | string | expected-value safety; prefer an activity over destructive long-text overwrite |
| first/last name, email, job title | string | existing exact Contact mapping; one changed field per Action |

Read-only, missing, deleted or type-changed HubSpot properties are rejected during
configuration or preview. Field mapping records store only the property name/type,
authority and configurer. The adapter updates exactly that stored property.

HubSpot pipelines and stages are discovered only when an admin opens advanced
mapping. RevenueOS stages are mapped one at a time; the system never guesses from
labels. Missing stage mapping makes the Action non-executable. Amount updates read
`deal_currency_code`; a different ISO currency fails without conversion. Contact
email is never invented and contact add/merge operations are not supported.

Recommended first setup is amount, close date, next step and any stages used by
the team. Other fields remain “Not mapped”. Methodology fields use the same future
typed mapping boundary but are not exposed in WO-025C.
