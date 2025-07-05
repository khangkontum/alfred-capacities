# Capacities Alfred Workflow

Alfred workflow for interacting with Capacities - search, save weblinks, and add notes directly from Alfred.

## Installation

1. Download the latest release from [GitHub Releases](https://github.com/khangkontum/alfred-capacities/releases)
2. Double-click the `.alfredworkflow` file to install
3. Configure your API token in Alfred workflow settings

## Commands

**Search**

```
cap <query>
```
Or use the configurable hotkey for quick access (see Configuration below)

**Save Weblink**

```
caps <url> [title]
```

**Add to Daily Note**

```
capn <text>
```

## Configuration

**Required: API Token**

1. Open Capacities → Settings → Capacities API
2. Generate an API token
3. In Alfred, right-click the workflow → Configure Workflow
4. Enter your API token in the "Capacities API Token" field

**Optional: Default Space ID**
In Alfred workflow settings, set "Default Space ID" field (get ID from Capacities app)

**Optional: Quick Search Hotkey**
1. In Alfred workflow settings, click the "Quick Search Hotkey" field
2. Press your desired key combination (e.g., ⌥+Space, ⌘+Shift+C)
3. The hotkey will open Alfred with "cap " pre-filled for quick note searching

## Troubleshooting

**Commands not working**: Verify API token is set in Alfred workflow settings
