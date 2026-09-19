# ReliefMesh frontend recovery

The original frontend is preserved on the `frontend` branch at `5a8365d`.

The unpushed UX pass was lost when the temporary workspace was cleaned. Recovery will extend this existing application, preserving its mock services, contracts, demo engine and both human approval gates.

Checkpoint plan:
1. Restore native-script language onboarding and persistent language selection.
2. Restore the visible decision dock, next actions, guided incident reading and compact laptop layout.
3. Restore state feedback, map interaction polish and accessible dialog behavior.
4. Run production build, TypeScript, automated tests and browser checks; document results.

The user has authorized incremental commits and pushes to `frontend`. Changes stay inside `frontend/`; `main` is not a publishing target.
