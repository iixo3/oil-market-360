from __future__ import annotations


RELATIONSHIP_GRAPH = {
    "nodes": [
        {"id": "shipping", "label": "Shipping stress", "x": 0.10, "y": 0.72},
        {"id": "physical", "label": "Physical premia", "x": 0.34, "y": 0.72},
        {"id": "east", "label": "East-of-Suez", "x": 0.34, "y": 0.42},
        {"id": "brentcl", "label": "Brent vs CL", "x": 0.58, "y": 0.62},
        {"id": "products", "label": "Product cracks", "x": 0.58, "y": 0.30},
        {"id": "cushing", "label": "Cushing / inland", "x": 0.58, "y": 0.88},
        {"id": "export", "label": "HTT / WTT", "x": 0.82, "y": 0.76},
        {"id": "grade", "label": "Sour / heavy", "x": 0.82, "y": 0.46},
    ],
    "edges": [
        {
            "source": "shipping",
            "target": "physical",
            "label": "possible transmission path",
            "explanation": "Higher freight and transit risk can raise the premium for prompt deliverable barrels.",
        },
        {
            "source": "physical",
            "target": "brentcl",
            "label": "possible transmission path",
            "explanation": "Stronger physical premia can widen Brent over CL when inland U.S. crude is relatively trapped.",
        },
        {
            "source": "physical",
            "target": "products",
            "label": "possible transmission path",
            "explanation": "Tighter prompt crude can feed through into product stress and crack expansion.",
        },
        {
            "source": "cushing",
            "target": "export",
            "label": "watch for divergence",
            "explanation": "Rising Cushing with firm export differentials points to inland pressure rather than global relief.",
        },
        {
            "source": "east",
            "target": "physical",
            "label": "rolling correlation",
            "explanation": "Oman/Dubai/Murban can reinforce broader physical premia when East-of-Suez stress is leading.",
        },
        {
            "source": "grade",
            "target": "products",
            "label": "possible transmission path",
            "explanation": "Sour/heavy scarcity can tighten refinery feedstock and increase downstream product stress.",
        },
    ],
}


def build_relationship_graph() -> dict:
    return RELATIONSHIP_GRAPH
