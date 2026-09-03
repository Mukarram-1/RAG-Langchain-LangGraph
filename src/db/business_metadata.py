"""Curated semantics that cannot be inferred from SQL types alone."""

BUSINESS_GLOSSARY = """
- "Domain": one website/domain legal case per row. Count domain cases here.
  "domainName" is the website hostname/URL; "companyName" is the legal business
  name; "dbaName" is an alternate business name.
  "visiteDate" is the initial visit date. "retestVisiteDate" is a text array
  containing revisit/retest dates (the database spelling is intentional).
- "Location": one physical-location legal case per row. Count physical cases
  here. "SubLocation" contains individual sites/defendants within a Location.
- "Domain"."client" joins "Client"."id". "Location"."client" joins
  "PhysicalClient"."id" (never "Client"."id"). These application-level IDs may
  use different SQL types, so compare both sides as text.
- "Settlements" stores website/domain settlements and joins
  "Settlements"."domain" to "Domain"."id" as text. "PhysicalSettlements"
  stores physical-case settlements and joins "locationId" to "Location"."id"
  as text.
- "Litigation"."domainId" joins "Domain"."id".
  "PhysicalLitigation"."locationId" joins "Location"."id".
- "BillingInvoice" may belong to either a domain case through "domainId" or a
  physical case through "locationId"; use only the branch relevant to the
  question.
- "MasterLeadList"."domainId" and "AttornayGenerateDocument"."domainId" join
  "Domain"."id" as text. Use "MasterLeadList"."domainName" =
  "Domain"."domainName" only as a fallback when no usable ID exists.
- "Domain"."originalDomainId" and "Domain"."masterDomainId" are self-relations
  to "Domain"."id". "Location"."originalLocationId" is a self-relation to
  "Location"."id".
- Do not treat "MasterLeadList"."client" as a reliable Client ID, and do not
  treat "AttornayGenerateDocument"."invoice" as a BillingInvoice ID.
- A user phrase containing LLC, Inc, Corp, company, or a business name usually
  refers to "companyName" or "dbaName", not "domainName". A hostname such as
  example.com refers to "domainName".
- For user-provided names, use ILIKE and search the appropriate alternate name
  fields with OR. Do not require exact case or punctuation unless the user
  explicitly requests an exact match. When punctuation may vary (apostrophes,
  commas, periods, smart quotes), build a wildcard from stable words, such as
  '%Scooter%Coffee%', instead of copying the full punctuated name.
- For counts, count the primary key column (for example COUNT("id")), because
  wildcard selection is intentionally blocked.
""".strip()
