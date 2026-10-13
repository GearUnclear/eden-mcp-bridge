# Validation and remaining acceptance

## Release candidate 1.2.0-rc.1

The repaired implementation passed **74 offline tests**: 16 protocol/catalogue, 12 persistence contracts, 23 reads/attributes, 12 integration/source, and 11 isolated DLL/client lifecycle. The release is rebuilt and checked from its own publication tree. Version labels and release metadata differ from the live-tested development build; runtime behavior is otherwise retained.

The runner `tools/run_offline_checks.py --transport` executes explicit suites in separate processes. The native DLL suite chooses a fresh UUID pipe and verifies the imported Python pipe before loading the DLL. It exercises real Windows transport while simulating the SQF side. Python fixtures and SQF delimiter/helper checks do not execute SQF in Arma. The additional 21-case SQF comparator script is included but has not been run as a suite.

## Observed live results

On the repaired development build, in disposable Lawn and Stratis scenarios:

- Empty pages, an entire 28-infantry page (`page_size=30`), and mixed empty-vehicle reads completed without field errors. One handler reported approximately 2ms; this is not an end-to-end benchmark.
- A loaded catalogue of 50,471 entries returned representative WEST/config-side1 and EAST/config-side0 classes correctly.
- Attribute discovery returned 43 candidates for vanilla infantry. Bulk reads returned 41 values and explicit nil errors for two unavailable properties. Playable/name aliases, skill, quotes, repeated backslashes, accented text, and Greek text round-tripped.
- Native grouping merged two units with verified destination membership and leadership. A separate object-page read confirmed the result. Native Undo emitted OnUndo and restored separate groups; Undo of a move restored the earlier height.
- Rotation at yaw123.5 passed precision-aware readback after the live-discovered comparison fix.
- ATL/ASL/terrain placement, two-coordinate z0, corrected marker creation, and fractional trigger height passed. A water marker returned ASL0 over terrain-142.91m. Water placement on land rejected.
- Mixed-side grouping, unknown attributes, and out-of-range skill rejected.
- A save request opened native Save As and returned unverified persistence. Cancellation worked. After a manual save, disk inspection confirmed variable, playable flag, skill, and quoted/Unicode description in mission.sqm.
- All six entities used for the final focused retest were deleted individually. The editor was empty and the bridge remained Ready.

The first live pass exposed null grouping response fields, an exact-rotation comparison false negative, a tiny trigger-height residual, and a marker-create height offset. Those fixes were rebuilt, deployed, and retested. These findings are why offline passes alone are not treated as complete engine acceptance.

## Still required

- Save through the bridge in a named scenario, reopen it, and verify grouping, routes, slots, and positions.
- Two complete 14-person squad merges, source-route/external-link protection, mounted-crew rejection, and target-route preservation in real Eden state.
- Preview return, load/new scenario and terrain-change recovery, including pending-request cancellation and no duplicate mutations.
- Remaining entity kinds, roof/structure placement, and the original modded 28-unit failure scenario.
- Broader conditional mod attributes, player/playable coupling, empty Undo history, and manual-edit interleaving.

The historical timeout's exact root cause remains unproven. The package contains bounded and more explicit error handling, but does not claim that all timeout scenarios or performance bottlenecks have been eliminated. Immediate readback is not disk persistence. The release remains a candidate while these cases are outstanding.
