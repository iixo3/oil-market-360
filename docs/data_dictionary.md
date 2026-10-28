# Data Dictionary

## Raw monitored fields

| Name | Source | Type | Frequency | Description | Why it matters | Fallback proxy |
| --- | --- | --- | --- | --- | --- | --- |
| CL | Exchange / broker | futures | intraday/daily | NYMEX WTI futures | Headline U.S. crude benchmark and inland paper signal | TradingView or IBKR CSV, else placeholder |
| BRENT | Exchange / broker | futures | intraday/daily | Canonical Brent paper benchmark displayed as Brent/BZ; direct IBKR may source it from the COIL contract family | Headline global seaborne benchmark | TradingView or IBKR CSV, else placeholder |
| AUB | Exchange / broker | futures proxy | intraday/daily | CME Dated Brent financial proxy | North Sea physical tightness proxy | Dated Brent if available, else placeholder |
| DATED_BRENT | Premium physical | assessment | daily | Prompt North Sea cargo benchmark | Closest truth-layer measure of prompt Atlantic physical stress | AUB |
| DBI | Exchange / broker or premium | futures proxy | intraday/daily | Dubai 1st Line proxy | East-of-Suez physical stress proxy | OQD |
| OQD | Exchange / broker | futures | intraday/daily | Canonical Oman crude benchmark for East-of-Suez stress; official benchmark materials commonly use OQD, while TradingView commonly surfaces a related Oman family as OMOIL | Gulf / Asia prompt crude replacement cost proxy | DBI or placeholder |
| ADM | Exchange / broker or premium | futures | intraday/daily | ICE Murban | East-of-Suez physical tightness proxy | OQD |
| HTT | Exchange / broker | differential | intraday/daily | WTI Houston vs WTI Trade Month | Export-barrel strength vs inland WTI weakness | placeholder |
| WTT | Exchange / broker | differential | intraday/daily | WTI Midland vs WTI Trade Month | Export-grade Midland strength | placeholder |
| YV | Exchange / broker | differential | intraday/daily | Mars vs WTI Trade Month | Sour/medium substitute tightness | placeholder |
| WHT | Exchange / broker | differential | intraday/daily | WCS Houston vs WTI Trade Month | Heavy crude replacement pressure | placeholder |
| RB | Exchange / broker | futures | intraday/daily | RBOB gasoline | Product-led stress and gasoline cracks | placeholder |
| HO | Exchange / broker | futures | intraday/daily | NY Harbor ULSD | Diesel/distillate tightness and freight-linked demand | placeholder |
| G | Exchange / broker | futures | intraday/daily | ICE low sulphur gasoil | European distillate stress | placeholder |
| BDTI | Freight / flow | index | intraday/daily | Baltic Dirty Tanker Index | Dirty tanker logistics and crude shipping stress | placeholder |
| BCTI | Freight / flow | index | intraday/daily | Baltic Clean Tanker Index | Clean-product shipping stress | placeholder |
| AIS_HORMUZ_TRANSITS | Freight / flow | flow count | intraday/daily | AIS transit count proxy | Whether cargoes are still moving through critical chokepoints | placeholder |
| WAR_RISK_PREMIUM | Freight / flow | premium proxy | intraday/daily | Insurance / war-risk proxy | Captures insurability friction and rerouting stress | placeholder |
| CUSHING | Public inventory | inventory | weekly | Cushing crude stocks | Shows inland pressure or relief in the U.S. | public CSV or placeholder |
| FUJAIRAH | Public inventory | inventory | weekly | Fujairah inventories | Shows Gulf storage absorption and Middle East stress | public CSV or placeholder |
| SINGAPORE | Public inventory | inventory | weekly | Singapore stocks | Asian balance and storage buffer | public CSV or placeholder |
| ARA | Public inventory | inventory | weekly | ARA product inventories | European product buffer and downstream tightness | public CSV or placeholder |

## Derived fields

| Name | Source | Type | Frequency | Description | Why it matters | Fallback proxy |
| --- | --- | --- | --- | --- | --- | --- |
| BRENT_CL_SPREAD | Local analytics | spread | derived | Brent minus CL | Seaborne stress vs inland U.S. stress | n/a |
| NORTHSEA_PHYSICAL_PREMIUM | Local analytics | spread | derived | AUB or Dated Brent relative to Brent futures | Checks whether physical North Sea tightness exceeds paper Brent | n/a |
| EAST_OF_SUEZ_PREMIUM | Local analytics | spread | derived | Average East-of-Suez proxies relative to Brent | Checks whether Gulf/Asia barrels are tightening faster than Atlantic paper | n/a |
| GASOLINE_CRACK_PROXY | Local analytics | crack proxy | derived | RBOB converted to barrel-equivalent minus CL | Gasoline-specific downstream stress | n/a |
| DIESEL_CRACK_PROXY | Local analytics | crack proxy | derived | ULSD converted to barrel-equivalent minus CL | Diesel/distillate downstream stress | n/a |
| GASOIL_CRACK_PROXY | Local analytics | crack proxy | derived | Gasoil barrel-equivalent minus Brent | European gasoil downstream stress | n/a |
| THREE_TWO_ONE_CRACK_PROXY | Local analytics | crack proxy | derived | Simplified 3:2:1 crack using RB, HO, and CL | Composite refinery margin proxy | n/a |

## Composite heuristics

| Name | Source | Type | Frequency | Description | Why it matters | Fallback proxy |
| --- | --- | --- | --- | --- | --- | --- |
| Paper vs Physical Stress Index | Local analytics | composite heuristic | derived | Blends physical-vs-paper spreads, freight stress, and flow friction | Distinguishes headline futures moves from genuine physical tightness | Uses available proxies and placeholders |
| East-of-Suez Stress Index | Local analytics | composite heuristic | derived | Blends Oman, Dubai, Murban, freight, and chokepoint indicators | Shows whether Gulf / Asia stress is leading the market | Uses available proxies and placeholders |
| U.S. Inland Dislocation Index | Local analytics | composite heuristic | derived | Blends HTT, WTT, Brent/CL, and Cushing pressure | Separates inland weakness from export-barrel strength | Uses available proxies and placeholders |
| Product Stress Index | Local analytics | composite heuristic | derived | Blends cracks, product futures, and product inventories | Shows whether the bottleneck is downstream rather than crude | Uses available proxies and placeholders |
| Sour/Heavy Substitution Index | Local analytics | composite heuristic | derived | Blends YV and WHT strength | Flags quality mismatch and substitution stress | Uses available proxies and placeholders |
| Logistics Constraint Index | Local analytics | composite heuristic | derived | Blends freight, AIS flows, and war-risk proxy | Shows transport and insurability friction | Uses available proxies and placeholders |
