"""Canned model responses keyed by scenario id.

Half are clean; half carry a *seeded grounding violation* so the scorer has
something to catch and the baseline rate lands below 100% — which is the whole
point of having a metric. Each violation is annotated.
"""

from __future__ import annotations

MOCK_RESPONSES: dict[str, str] = {
    # --- clean ---
    "classic_rich": """
{"suggestions":[
  {"name":"Boulevardier","description":"Bittersweet, stirred, spirit-forward.",
   "ingredients":[
     {"name":"Four Roses Small Batch","quantity":"1.5 oz","source":"inventory"},
     {"name":"Campari","quantity":"1 oz","source":"inventory"},
     {"name":"Carpano Antica Sweet Vermouth","quantity":"1 oz","source":"inventory"},
     {"name":"orange peel","quantity":"1","source":"perishable"}],
   "steps":["Stir with ice","Strain over a large cube","Express orange peel"],
   "why":"Uses your bourbon, Campari and sweet vermouth — all on hand."},
  {"name":"Improved Whiskey Cocktail","description":"Rye-forward and aromatic.",
   "ingredients":[
     {"name":"Rittenhouse Rye","quantity":"2 oz","source":"inventory"},
     {"name":"Angostura Bitters","quantity":"2 dashes","source":"inventory"},
     {"name":"demerara syrup","quantity":"1 tsp","source":"pantry"}],
   "steps":["Stir with ice","Strain into a chilled glass"],
   "why":"Spirit-forward and entirely from your shelf."}
]}""",

    "negroni_no_sweet": """
{"suggestions":[
  {"name":"Boulevardier","description":"Bitter, stirred, not sweet.",
   "ingredients":[
     {"name":"Rittenhouse Rye","quantity":"1.5 oz","source":"inventory"},
     {"name":"Campari","quantity":"1 oz","source":"inventory"},
     {"name":"Carpano Antica Sweet Vermouth","quantity":"1 oz","source":"inventory"}],
   "steps":["Stir with ice","Strain over ice"],
   "why":"Bitter-forward and stirred, per your constraints."}
]}""",

    "sparse_old_fashioned": """
{"suggestions":[
  {"name":"Bourbon Old Fashioned","description":"Classic, warming nightcap.",
   "ingredients":[
     {"name":"Four Roses Small Batch","quantity":"2 oz","source":"inventory"},
     {"name":"demerara syrup","quantity":"1 tsp","source":"pantry"},
     {"name":"Angostura Bitters","quantity":"2 dashes","source":"missing"},
     {"name":"orange peel","quantity":"1","source":"perishable"}],
   "steps":["Stir with ice","Strain over a large cube","Express orange peel"],
   "why":"You have the bourbon; you'll need bitters to finish it properly."}
]}""",

    "movie_night": """
{"suggestions":[
  {"name":"Mezcal Old Fashioned","description":"Smoky, cozy, low-effort.",
   "ingredients":[
     {"name":"Del Maguey Vida Mezcal","quantity":"2 oz","source":"inventory"},
     {"name":"Angostura Bitters","quantity":"2 dashes","source":"inventory"},
     {"name":"demerara syrup","quantity":"1 tsp","source":"pantry"},
     {"name":"orange peel","quantity":"1","source":"perishable"}],
   "steps":["Stir with ice","Strain over a large cube"],
   "why":"Cozy and smoky, all from your shelf."}
]}""",

    # --- seeded violations ---

    # VIOLATION: "white rum" claimed as inventory but not owned (hallucinated ownership).
    "tiki_adversarial": """
{"suggestions":[
  {"name":"Bourbon Daiquiri Riff","description":"A tropical-ish stand-in.",
   "ingredients":[
     {"name":"Four Roses Small Batch","quantity":"1.5 oz","source":"inventory"},
     {"name":"white rum","quantity":"0.5 oz","source":"inventory"},
     {"name":"lime juice","quantity":"0.75 oz","source":"perishable"},
     {"name":"simple syrup","quantity":"0.5 oz","source":"pantry"}],
   "steps":["Shake with ice","Strain into a coupe"],
   "why":"Tries to fake a tiki vibe — but you don't own rum."}
]}""",

    # VIOLATION: "agave syrup" claimed as pantry (not an allowed staple → assuming an item you may not have).
    "companion_mezcal": """
{"suggestions":[
  {"name":"Naked & Smoky","description":"Smoky and spirit-forward for your wife.",
   "ingredients":[
     {"name":"Del Maguey Vida Mezcal","quantity":"2 oz","source":"inventory"},
     {"name":"Angostura Bitters","quantity":"2 dashes","source":"inventory"},
     {"name":"agave syrup","quantity":"1 tsp","source":"pantry"}],
   "steps":["Stir with ice","Strain over a large cube"],
   "why":"Smoky, not sweet — matches her taste."}
]}""",

    # VIOLATION: "Tequila Blanco" claimed as inventory but not owned.
    "margarita_no_tequila": """
{"suggestions":[
  {"name":"Classic Margarita","description":"Bright and citrusy.",
   "ingredients":[
     {"name":"Tequila Blanco","quantity":"2 oz","source":"inventory"},
     {"name":"Cointreau","quantity":"1 oz","source":"inventory"},
     {"name":"lime juice","quantity":"1 oz","source":"perishable"},
     {"name":"salt","quantity":"rim","source":"pantry"}],
   "steps":["Shake with ice","Strain into a salted-rim glass"],
   "why":"Citrusy and crisp."}
]}""",

    # Mixed: drink 1 grounded; drinks 2 & 3 pad with a hallucinated bottle each.
    "impossible_count": """
{"suggestions":[
  {"name":"Bourbon Old Fashioned","description":"The honest pick.",
   "ingredients":[
     {"name":"Four Roses Small Batch","quantity":"2 oz","source":"inventory"},
     {"name":"simple syrup","quantity":"1 tsp","source":"pantry"},
     {"name":"Angostura Bitters","quantity":"2 dashes","source":"missing"}],
   "steps":["Stir","Strain over a cube"],
   "why":"Made from your one bottle, bitters flagged missing."},
  {"name":"Whiskey Sour","description":"Padding suggestion.",
   "ingredients":[
     {"name":"Four Roses Small Batch","quantity":"2 oz","source":"inventory"},
     {"name":"lemon juice","quantity":"0.75 oz","source":"perishable"},
     {"name":"simple syrup","quantity":"0.75 oz","source":"pantry"},
     {"name":"egg white","quantity":"1","source":"perishable"}],
   "steps":["Dry shake","Shake with ice","Strain"],
   "why":"Fine, but padding the count."},
  {"name":"Manhattan","description":"Padding with a bottle you don't own.",
   "ingredients":[
     {"name":"Four Roses Small Batch","quantity":"2 oz","source":"inventory"},
     {"name":"sweet vermouth","quantity":"1 oz","source":"pantry"},
     {"name":"Angostura Bitters","quantity":"2 dashes","source":"missing"}],
   "steps":["Stir","Strain"],
   "why":"Hallucinates vermouth as pantry to hit count=3."}
]}""",

    # VIOLATION: "Gin" faked as inventory (not owned).
    "negroni_no_gin": """
{"suggestions":[
  {"name":"Negroni","description":"Classic bitter aperitivo.",
   "ingredients":[
     {"name":"Gin","quantity":"1 oz","source":"inventory"},
     {"name":"Campari","quantity":"1 oz","source":"inventory"},
     {"name":"Carpano Antica Sweet Vermouth","quantity":"1 oz","source":"inventory"},
     {"name":"orange peel","quantity":"1","source":"perishable"}],
   "steps":["Stir with ice","Strain over a large cube"],
   "why":"Mock fakes gin as owned."}
]}""",

    # VIOLATION: Peychaud's + absinthe faked as inventory.
    "sazerac_no_peychauds": """
{"suggestions":[
  {"name":"Sazerac","description":"New Orleans classic.",
   "ingredients":[
     {"name":"Rittenhouse Rye","quantity":"2 oz","source":"inventory"},
     {"name":"Peychaud's Bitters","quantity":"3 dashes","source":"inventory"},
     {"name":"Absinthe","quantity":"rinse","source":"inventory"},
     {"name":"sugar","quantity":"1 cube","source":"pantry"}],
   "steps":["Rinse with absinthe","Stir rye, sugar, bitters","Strain"],
   "why":"Mock fakes Peychaud's and absinthe as owned."}
]}""",

    # VIOLATION: rum + curacao faked as inventory, orgeat faked as pantry.
    "mai_tai_bourbon_only": """
{"suggestions":[
  {"name":"Mai Tai","description":"Tiki classic.",
   "ingredients":[
     {"name":"Aged Rum","quantity":"2 oz","source":"inventory"},
     {"name":"Orange Curacao","quantity":"0.5 oz","source":"inventory"},
     {"name":"Orgeat","quantity":"0.5 oz","source":"pantry"},
     {"name":"lime juice","quantity":"1 oz","source":"perishable"}],
   "steps":["Shake with crushed ice"],
   "why":"Mock fakes rum/curacao as owned and orgeat as pantry."}
]}""",

    # Drinks 1-3 grounded; drinks 4-5 pad with faked bottles.
    "high_count_pad": """
{"suggestions":[
  {"name":"Bourbon Old Fashioned","description":"Honest.",
   "ingredients":[{"name":"Four Roses Small Batch","quantity":"2 oz","source":"inventory"},{"name":"sugar","quantity":"1 tsp","source":"pantry"},{"name":"Angostura Bitters","quantity":"2 dashes","source":"missing"}],
   "steps":["Stir"],"why":"Honest."},
  {"name":"Rye, neat","description":"Honest.",
   "ingredients":[{"name":"Rittenhouse Rye","quantity":"2 oz","source":"inventory"}],
   "steps":["Pour"],"why":"Honest."},
  {"name":"Mezcal, neat","description":"Honest.",
   "ingredients":[{"name":"Del Maguey Vida Mezcal","quantity":"2 oz","source":"inventory"}],
   "steps":["Pour"],"why":"Honest."},
  {"name":"Gin Martini","description":"Padding with faked bottles.",
   "ingredients":[{"name":"Gin","quantity":"2.5 oz","source":"inventory"},{"name":"Dry Vermouth","quantity":"0.5 oz","source":"inventory"}],
   "steps":["Stir"],"why":"Fakes gin and dry vermouth as owned."},
  {"name":"Daiquiri","description":"Padding with faked rum.",
   "ingredients":[{"name":"White Rum","quantity":"2 oz","source":"inventory"},{"name":"lime juice","quantity":"0.75 oz","source":"perishable"},{"name":"simple syrup","quantity":"0.5 oz","source":"pantry"}],
   "steps":["Shake"],"why":"Fakes rum as owned."}
]}""",
}
