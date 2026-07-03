title = "Mattermost sync backend"
description = f"""
{title}. 🚀

## Features
- LDAP group synchronization with Mattermost teams
- Automated periodic sync
- Detailed logging and error tracking

## Technical Details
#### Authentication
- Supports LDAP and Mattermost API tokens
#### Configuration
- Flexible sync rules configuration
#### Monitoring
- Integration with Sentry for error tracking
- Performance metrics collection
"""

# Service information
Mattermost_LDAP_Group_Sync = "Mattermost LDAP Group Sync"
GitHub_Repo = "Python Mattermost LDAP Sync"

service_description = """
Service for automatic synchronization of LDAP groups with Mattermost via API

🌟 Key Features
🛠 Functionality    📝 Description
LDAP Integration    Get current list of groups and user memberships from LDAP
Mattermost API      Manage teams and memberships through Mattermost API
Smart Sync          Compare data and apply targeted changes
Error Tracking      Sentry integration for error monitoring

📊 Solution Architecture
graph LR
    A[LDAP Server] --> B[Sync Service]
    B --> C[Mattermost API]
    B --> D[Sentry]
"""
