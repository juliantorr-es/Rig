# Public Command Contract

If a command appears in public help, it must work or be explicitly marked preview.

## Public Stable

- `rig init`
- `rig status`
- `rig config inspect`
- `rig doctor`
- `rig doctor queue`
- `rig doctor deps`
- `rig job create`
- `rig job list`
- `rig job inspect`
- `rig job run`
- `rig job cancel`
- `rig job retry`
- `rig run`
- `rig debug bundle`
- `rig log list`
- `rig log show`
- `rig log tail`
- `rig workspace list`
- `rig workspace inspect`
- `rig workspace review`
- `rig workspace apply`

## Public Preview

- `rig tui --gridline`
- `rig tui --chat`
- `rig provider connect`
- `rig provider test`
- `rig model recommend`
- `rig benchmark run`

## Advanced

- `rig release check`
- `rig context build`
- `rig context inspect`
- `rig context explain`
- `rig system inspect`
- `rig runtime list`
- `rig runtime inspect`
- `rig model list`
- `rig model register`
- `rig model verify`

## Dev / Internal

- raw schema tools
- scheduler / supervisor / swarm modules
- legacy `work_queue.py`
- migration helpers

## Deprecated Aliases

- `rig window open` -> `rig tui --window`

## Blocked From Public Help

- direct shell execution
- direct provider mutation
- auto-apply
- legacy migration repair by default
