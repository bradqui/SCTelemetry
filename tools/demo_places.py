"""Where the bundled recordings were made, for the demos (tools/demo_cockpit.py and
demo_fleet.py).

The recordings predate the Game.log lines Starglance now reads for "At Lorville" and
"Flying at Hurston" (decision 26), so the demos add them: the recordings in Hurston's
jurisdiction were made around Hurston, and the on-foot ones in Lorville (as their captures'
logs say). Two place names stand in for the game's own text file, which the demos don't
have.
"""

from __future__ import annotations

from starglance.places import Names

NAMES = Names({"stanton1": "Hurston", "stanton1_lorville": "Lorville"})
AT_HURSTON = {
    "constellation-pilot-copilot-turret",
    "cruise-nav-scm",
    "hangar-landing-refuel",
    "on-foot",
    "on-foot-helmet",
    "quantum-travel",
    "sit-power-takeoff-gear",
}
IN_LORVILLE = {"on-foot", "on-foot-helmet"}
TS = "<2026-11-23T18:00:00.000Z>"


def add_places(pipeline, fixture: str) -> None:
    """Where this recording was made, as Game.log would have said (state only, no events)."""
    pipeline.set_names(NAMES)
    if fixture in AT_HURSTON:
        cells = f"{TS}   planet cells:   64 [16384] meshes: 0 [0] name: OOC_Stanton_1_Hurston"
        pipeline.on_log(cells, 0, True)
    if fixture in IN_LORVILLE:
        pipeline.on_log(
            f"{TS} [Notice] <RequestLocationInventory> Player[Demo] requested inventory for "
            "Location[Stanton1_Lorville] [Team_CoreGameplayFeatures][Inventory]",
            0,
            True,
        )
