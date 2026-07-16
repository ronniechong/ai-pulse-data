"""Static country -> region crosswalk for the M3 geo panel's 8-region bucket
grid (design brief's own choice: North America, Europe, East Asia, South
Asia, SE Asia, Middle East, Latin America, Africa). Covers both alpha-3
codes (geo-adoption.json, Anthropic Economic Index) and alpha-2 codes
(sdk-geo.json, ClickPy/PyPI) so both data sources aggregate into the same
8 buckets.

One-time hand-authored table, not an external taxonomy library (M2.6
decision — see work-docs). Judgment calls worth documenting:
- "Middle East" bucket is broad: MENA (incl. Egypt/Maghreb) + Turkey +
  Caucasus + Central Asia. No dedicated bucket exists for those groups in
  the design's 8 regions, and Middle East was the closest cultural/regional
  fit.
- Russia and the Caucasus/Central Asian states are geographically
  transcontinental; placed by the same MENA-adjacent convention above
  (Caucasus/Central Asia -> Middle East) except Russia itself -> Europe
  (standard convention in most simplified region schemes).
- The design's 8 regions have **no Oceania/Pacific bucket** (Australia, NZ,
  Pacific islands) and no bucket for uninhabited/non-country codes (e.g.
  Antarctica, the EU aggregate code ClickPy sometimes reports). Rather than
  force these into an unrelated bucket, they're intentionally left
  unmapped — region_of() returns None and callers should log/skip, not
  silently misclassify. Revisit if a real panel ends up needing Oceania.
"""

REGIONS = (
    "North America",
    "Europe",
    "East Asia",
    "South Asia",
    "SE Asia",
    "Middle East",
    "Latin America",
    "Africa",
)

_NORTH_AMERICA = {"US", "CA"}

_EUROPE = {
    "AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CY", "CZ", "DK", "EE", "FO", "FI", "FR",
    "DE", "GI", "GR", "GG", "HU", "IS", "IE", "IM", "IT", "JE", "XK", "LV", "LI", "LT", "LU",
    "MT", "MD", "MC", "ME", "NL", "MK", "NO", "PL", "PT", "RO", "RU", "SM", "RS", "SK", "SI",
    "ES", "SJ", "SE", "CH", "UA", "GB", "VA", "AX", "GL",
}

_MIDDLE_EAST = {
    "AE", "AF", "AM", "AZ", "BH", "EG", "GE", "IR", "IQ", "IL", "JO", "KZ", "KW", "KG", "LB",
    "LY", "MA", "OM", "PS", "QA", "SA", "SY", "TJ", "TN", "TR", "TM", "UZ", "YE", "DZ", "SD",
}

_EAST_ASIA = {"CN", "HK", "MO", "TW", "JP", "KR", "KP", "MN"}

_SOUTH_ASIA = {"IN", "PK", "BD", "LK", "NP", "BT", "MV"}

_SE_ASIA = {"ID", "MY", "TH", "VN", "PH", "SG", "MM", "KH", "LA", "BN", "TL"}

_LATIN_AMERICA = {
    "MX", "GT", "BZ", "SV", "HN", "NI", "CR", "PA", "CO", "VE", "GY", "SR", "EC", "PE", "BR",
    "BO", "PY", "CL", "AR", "UY",
    # Caribbean
    "CU", "DO", "HT", "JM", "TT", "BB", "BS", "GD", "LC", "VC", "KN", "AG", "DM", "PR", "VI",
    "VG", "AI", "MS", "KY", "TC", "BM", "AW", "CW", "SX", "BQ", "GP", "MQ", "GF", "BL", "MF",
    "FK",
}

_AFRICA = {
    "NG", "ZA", "KE", "ET", "GH", "TZ", "UG", "ZM", "ZW", "MZ", "AO", "CM", "CI", "SN", "ML",
    "BF", "NE", "TD", "RW", "BI", "SS", "SO", "ER", "DJ", "LR", "SL", "GN", "GW", "GM", "MR",
    "TG", "BJ", "GA", "CG", "CD", "CF", "GQ", "ST", "CV", "NA", "BW", "LS", "SZ", "MW", "MG",
    "MU", "SC", "KM", "YT", "RE", "SH", "EH",
}

_ALPHA2_TO_REGION: dict[str, str] = {}
for _codes, _region in (
    (_NORTH_AMERICA, "North America"),
    (_EUROPE, "Europe"),
    (_MIDDLE_EAST, "Middle East"),
    (_EAST_ASIA, "East Asia"),
    (_SOUTH_ASIA, "South Asia"),
    (_SE_ASIA, "SE Asia"),
    (_LATIN_AMERICA, "Latin America"),
    (_AFRICA, "Africa"),
):
    for _code in _codes:
        _ALPHA2_TO_REGION[_code] = _region

# alpha-3 equivalents for the same classification (geo-adoption.json uses
# alpha-3). Hand-mapped once against the ISO 3166-1 alpha-2/alpha-3 pairing.
_ALPHA2_TO_ALPHA3 = {
    "US": "USA", "CA": "CAN", "AL": "ALB", "AD": "AND", "AT": "AUT", "BY": "BLR", "BE": "BEL",
    "BA": "BIH", "BG": "BGR", "HR": "HRV", "CY": "CYP", "CZ": "CZE", "DK": "DNK", "EE": "EST",
    "FO": "FRO", "FI": "FIN", "FR": "FRA", "DE": "DEU", "GI": "GIB", "GR": "GRC", "GG": "GGY",
    "HU": "HUN", "IS": "ISL", "IE": "IRL", "IM": "IMN", "IT": "ITA", "JE": "JEY", "XK": "XKX",
    "LV": "LVA", "LI": "LIE", "LT": "LTU", "LU": "LUX", "MT": "MLT", "MD": "MDA", "MC": "MCO",
    "ME": "MNE", "NL": "NLD", "MK": "MKD", "NO": "NOR", "PL": "POL", "PT": "PRT", "RO": "ROU",
    "RU": "RUS", "SM": "SMR", "RS": "SRB", "SK": "SVK", "SI": "SVN", "ES": "ESP", "SJ": "SJM",
    "SE": "SWE", "CH": "CHE", "UA": "UKR", "GB": "GBR", "VA": "VAT", "AX": "ALA", "GL": "GRL",
    "AE": "ARE", "AF": "AFG", "AM": "ARM", "AZ": "AZE", "BH": "BHR", "EG": "EGY", "GE": "GEO",
    "IR": "IRN", "IQ": "IRQ", "IL": "ISR", "JO": "JOR", "KZ": "KAZ", "KW": "KWT", "KG": "KGZ",
    "LB": "LBN", "LY": "LBY", "MA": "MAR", "OM": "OMN", "PS": "PSE", "QA": "QAT", "SA": "SAU",
    "SY": "SYR", "TJ": "TJK", "TN": "TUN", "TR": "TUR", "TM": "TKM", "UZ": "UZB", "YE": "YEM",
    "DZ": "DZA", "SD": "SDN", "CN": "CHN", "HK": "HKG", "MO": "MAC", "TW": "TWN", "JP": "JPN",
    "KR": "KOR", "KP": "PRK", "MN": "MNG", "IN": "IND", "PK": "PAK", "BD": "BGD", "LK": "LKA",
    "NP": "NPL", "BT": "BTN", "MV": "MDV", "ID": "IDN", "MY": "MYS", "TH": "THA", "VN": "VNM",
    "PH": "PHL", "SG": "SGP", "MM": "MMR", "KH": "KHM", "LA": "LAO", "BN": "BRN", "TL": "TLS",
    "MX": "MEX", "GT": "GTM", "BZ": "BLZ", "SV": "SLV", "HN": "HND", "NI": "NIC", "CR": "CRI",
    "PA": "PAN", "CO": "COL", "VE": "VEN", "GY": "GUY", "SR": "SUR", "EC": "ECU", "PE": "PER",
    "BR": "BRA", "BO": "BOL", "PY": "PRY", "CL": "CHL", "AR": "ARG", "UY": "URY", "CU": "CUB",
    "DO": "DOM", "HT": "HTI", "JM": "JAM", "TT": "TTO", "BB": "BRB", "BS": "BHS", "GD": "GRD",
    "LC": "LCA", "VC": "VCT", "KN": "KNA", "AG": "ATG", "DM": "DMA", "PR": "PRI", "VI": "VIR",
    "VG": "VGB", "AI": "AIA", "MS": "MSR", "KY": "CYM", "TC": "TCA", "BM": "BMU", "AW": "ABW",
    "CW": "CUW", "SX": "SXM", "BQ": "BES", "GP": "GLP", "MQ": "MTQ", "GF": "GUF", "BL": "BLM",
    "MF": "MAF", "FK": "FLK", "NG": "NGA", "ZA": "ZAF", "KE": "KEN", "ET": "ETH", "GH": "GHA",
    "TZ": "TZA", "UG": "UGA", "ZM": "ZMB", "ZW": "ZWE", "MZ": "MOZ", "AO": "AGO", "CM": "CMR",
    "CI": "CIV", "SN": "SEN", "ML": "MLI", "BF": "BFA", "NE": "NER", "TD": "TCD", "RW": "RWA",
    "BI": "BDI", "SS": "SSD", "SO": "SOM", "ER": "ERI", "DJ": "DJI", "LR": "LBR", "SL": "SLE",
    "GN": "GIN", "GW": "GNB", "GM": "GMB", "MR": "MRT", "TG": "TGO", "BJ": "BEN", "GA": "GAB",
    "CG": "COG", "CD": "COD", "CF": "CAF", "GQ": "GNQ", "ST": "STP", "CV": "CPV", "NA": "NAM",
    "BW": "BWA", "LS": "LSO", "SZ": "SWZ", "MW": "MWI", "MG": "MDG", "MU": "MUS", "SC": "SYC",
    "KM": "COM", "YT": "MYT", "RE": "REU", "SH": "SHN", "EH": "ESH",
}

_ALPHA3_TO_REGION: dict[str, str] = {
    _ALPHA2_TO_ALPHA3[_a2]: _region for _a2, _region in _ALPHA2_TO_REGION.items() if _a2 in _ALPHA2_TO_ALPHA3
}


def region_of(country_code: str) -> str | None:
    """Region for an alpha-2 or alpha-3 country code, or None if the code
    isn't classified (Oceania/Pacific, non-country aggregates like 'EU',
    uninhabited territories — see module docstring). Callers should skip
    and log unclassified codes, never guess a bucket."""
    code = country_code.upper()
    if len(code) == 2:
        return _ALPHA2_TO_REGION.get(code)
    if len(code) == 3:
        return _ALPHA3_TO_REGION.get(code)
    return None
