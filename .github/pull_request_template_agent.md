# Agent Pull Request

## Scope

<!-- Describe the smallest coherent change this agent submission makes. -->

## Non-Goals

<!-- State what this PR intentionally does not change. -->

## Touched Systems

- [ ] Replay / receipts
- [ ] Topology / workspace lifecycle
- [ ] Frontend / projections / UI
- [ ] Governance / branch policy
- [ ] CI / validation workflows
- [ ] Documentation only

## Replay Impact

- [ ] No replay impact
- [ ] Replay-sensitive
- [ ] Affects deterministic reconstruction
- [ ] Changes receipt or event ordering
- [ ] Requires replay validation evidence

## Topology Impact

- [ ] No topology impact
- [ ] Affects workspace topology
- [ ] Affects agent topology
- [ ] Affects runtime topology
- [ ] Requires topology integrity review

## Frontend Contract Impact

- [ ] No frontend contract impact
- [ ] Affects widget export surface
- [ ] Affects renderer signatures
- [ ] Affects projection contracts
- [ ] Affects reduced-motion or disclosure behavior

## Doctrine Impact

- [ ] No doctrine impact
- [ ] Changes governance posture
- [ ] Changes merge authority
- [ ] Changes protected-branch behavior
- [ ] Changes human review requirements

## Validation Commands Run

- [ ] `python3.14 -m compileall -q src tests`
- [ ] `python3.14 -m pyright --project pyrightconfig.json`
- [ ] `python3.14 -m pytest tests/test_frontend_contracts.py -v`
- [ ] `python3.14 -m pytest tests/test_replay.py -v`
- [ ] `python3.14 -m pytest tests/test_ui_frontend_logic.py -v`
- [ ] `python3.14 -m rig doctor`
- [ ] `python3.14 -m rig ui --help`
- [ ] `python3.14 -m rig --debug ui --browser`
- [ ] `bash scripts/check.sh --fast`

## Runtime Behavior Changes

<!-- Describe any user-visible or operational behavior changes. -->

## Risk Assessment

- [ ] Low risk
- [ ] Moderate risk
- [ ] High risk

### What could fail

<!-- Call out replay drift, contract drift, topology drift, or merge-gate drift. -->

## Replay-Safe Checklist

- [ ] Deterministic behavior preserved
- [ ] Replay ordering preserved
- [ ] No hidden state added
- [ ] No new non-deterministic data source introduced

## Topology Governance Checklist

- [ ] Branch routing remains explicit
- [ ] Protected branches remain protected
- [ ] No direct path to `main`
- [ ] No semantic drift in topology labels or branch roles

## Frontend Contract Checklist

- [ ] Widget exports remain complete
- [ ] Renderer signatures remain consistent
- [ ] Registry remains deterministic
- [ ] Disclosure / reduced-motion participation remains intact

## Motion / Disclosure Governance Checklist

- [ ] No hidden auto-advance behavior
- [ ] Reduced-motion path preserved
- [ ] User-visible motion remains truthful
- [ ] Disclosure behavior remains explicit

## Notes for Reviewers

<!-- Link any debug artifacts, soak logs, or replay summaries here. -->
