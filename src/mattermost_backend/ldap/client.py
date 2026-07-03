from typing import Any, Dict, List, Optional, Union

import ldap3


class LDAPConnectionError(Exception):
    """Custom exception for LDAP connection issues."""

    pass


class LDAPClient:
    def __init__(self, server: str, user: str, password: str, base_dn: str):
        """Initialize LDAP client with connection parameters.

        Args:
            server: LDAP server address (e.g., 'ldap://example.com').
            user: Bind user DN (e.g., 'cn=admin,dc=example,dc=com').
            password: Bind user password.
            base_dn: Base DN for searches (e.g., 'dc=example,dc=com').
        """
        self.server = server
        self.user = user
        self.password = password
        self.base_dn = base_dn
        self.connection: Optional[ldap3.Connection] = None

    def _ensure_connection(self) -> None:
        """Ensure the LDAP connection is established and bound."""
        if not self.connection or not self.connection.bound:
            raise LDAPConnectionError("LDAP connection is not established.")

    def connect(self) -> None:
        """Establish connection to LDAP server."""
        try:
            server = ldap3.Server(self.server)
            self.connection = ldap3.Connection(
                server,
                user=self.user,
                password=self.password,
                auto_bind=True,
            )
        except Exception as e:
            self.connection = None
            raise LDAPConnectionError(f"Failed to connect to LDAP: {e}") from e

    def _search(
        self,
        search_filter: str,
        attributes: List[str],
        search_base: Optional[str] = None,
        search_scope: str = ldap3.SUBTREE,
    ) -> List[ldap3.Entry]:
        """Perform a generic LDAP search.

        Args:
            search_filter: LDAP search filter.
            attributes: List of attributes to retrieve.
            search_base: Base DN for the search (defaults to self.base_dn).
            search_scope: Search scope (defaults to SUBTREE).

        Returns:
            List of LDAP entries matching the search.
        """
        self._ensure_connection()

        base = search_base if search_base is not None else self.base_dn
        self.connection.search(
            search_base=base,
            search_filter=search_filter,
            attributes=attributes,
            search_scope=search_scope,
        )
        return list(self.connection.entries)

    def get_groups(self, search_filter: str = "(objectClass=group)") -> List[ldap3.Entry]:
        """Retrieve groups from LDAP.

        Args:
            search_filter: LDAP filter for groups (default: all groups).

        Returns:
            List of group entries.
        """
        return self._search(search_filter, ["cn", "member"])

    def get_enabled_users(self) -> List[Dict[str, str]]:
        """Retrieve enabled users from Active Directory with their Name and SamAccountName.

        Returns:
            List of dictionaries with user information.
            Example: [{'Name': 'John Doe', 'SamAccountName': 'jdoe'}]
        """
        search_filter = (
            "(&(objectClass=user)"
            "(objectCategory=person)"
            "(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
        )
        entries = self._search(search_filter, ["name", "sAMAccountName"])

        return [
            {
                "Name": entry.name.value if hasattr(entry, "name") else "",
                "SamAccountName": (
                    entry.sAMAccountName.value if hasattr(entry, "sAMAccountName") else ""
                ),
            }
            for entry in entries
        ]

    def get_group_ad(self) -> List[Dict[str, Union[str, List[str]]]]:
        """Retrieve enabled users from Active Directory with their groups.

        Returns:
            List of dictionaries with user information and their groups.
            Example: [{
                'Name': 'John Doe',
                'SamAccountName': 'jdoe',
                'Groups': ['Group1', 'Group2']
            }]
        """
        search_filter = (
            "(&(objectClass=user)"
            "(objectCategory=person)"
            "(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
        )
        entries = self._search(search_filter, ["name", "sAMAccountName", "memberOf"])

        users = []
        for entry in entries:
            groups = []
            if hasattr(entry, "memberOf"):
                groups = [group_dn.split(",")[0][3:] for group_dn in entry.memberOf.values]

            users.append(
                {
                    "Name": entry.name.value if hasattr(entry, "name") else "",
                    "SamAccountName": (
                        entry.sAMAccountName.value if hasattr(entry, "sAMAccountName") else ""
                    ),
                    "Groups": groups,
                }
            )

        return users

    def get_mattermost_groups(
        self,
        prefix: str = "Mattermost",
        attributes: Optional[List[str]] = None,
        search_base: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve all groups starting with a specific prefix.

        Args:
            prefix: Filter groups starting with this string (default: 'Mattermost').
            attributes: LDAP attributes to fetch (default: ['cn', 'distinguishedName']).
            search_base: Base DN to search (default: self.base_dn).

        Returns:
            List of dictionaries with group attributes.
            Example: [{
                'cn': 'Mattermost_Admins',
                'distinguishedName': 'CN=Mattermost_Admins,OU=Groups,...'
            }]
        """
        if attributes is None:
            attributes = ["cn", "distinguishedName"]

        search_filter = f"(&(objectClass=group)(cn={prefix}*))"
        entries = self._search(search_filter, attributes, search_base)

        groups = []
        for entry in entries:
            group_data = {
                attr: (entry[attr].value if hasattr(entry[attr], "value") else entry[attr])
                for attr in attributes
                if attr in entry
            }
            groups.append(group_data)

        return groups

    def get_users_from_mattermost_groups(
        self,
        group_prefix: str = "Mattermost",
        user_attributes: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve all users from groups starting with prefix in single optimized query.

        Args:
            group_prefix: Prefix for group names (default: 'Mattermost').
            user_attributes: Attributes to fetch for users (default: basic attributes).

        Returns:
            Dictionary mapping group names to their member users.
            Example: {
                'Mattermost_Admins': [{'sAMAccountName': 'user1', ...}],
                ...
            }
        """
        if user_attributes is None:
            user_attributes = ["sAMAccountName", "displayName", "distinguishedName"]

        mattermost_groups = self.get_mattermost_groups(
            prefix=group_prefix, attributes=["cn", "member"]
        )

        all_user_dns = set()
        group_members = {}

        for group in mattermost_groups:
            group_name = group["cn"]
            members = group.get("member", []) or []
            group_members[group_name] = members
            all_user_dns.update(members)

        if not all_user_dns:
            return {}

        user_dn_filter = "(|" + "".join(f"(distinguishedName={dn})" for dn in all_user_dns) + ")"
        search_filter = f"(&(objectClass=user){user_dn_filter})"

        entries = self._search(search_filter, user_attributes)

        users_data = {
            entry.distinguishedName.value: {
                attr: entry[attr].value if attr in entry else None for attr in user_attributes
            }
            for entry in entries
            if hasattr(entry, "distinguishedName")
        }

        return {
            group_name: [users_data[dn] for dn in members if dn in users_data]
            for group_name, members in group_members.items()
        }

    def get_mattermost_groups_for_group_access(self) -> List[Dict[str, Any]]:
        """Retrieve all groups from Mattermost OU in specific AD structure.

        Returns:
            List of dictionaries with group information.
            Example: [{
                'name': 'Group1',
                'dn': 'CN=Group1,...',
                'members': ['DN1', 'DN2'],
                'description': 'Group description'
            }]
        """
        search_base = "OU=Mattermost,OU=Access,OU=Groups,OU=Saber3D,DC=SABER3D,DC=NET"
        entries = self._search(
            "(objectClass=group)",
            ["cn", "distinguishedName", "member", "description"],
            search_base,
        )

        return [
            {
                "name": entry.cn.value,
                "dn": entry.distinguishedName.value,
                "members": (list(entry.member.values) if hasattr(entry, "member") else []),
                "description": (entry.description.value if hasattr(entry, "description") else None),
            }
            for entry in entries
        ]

    def get_mattermost_groups_with_users(self) -> List[Dict[str, Any]]:
        """Retrieve all Mattermost groups with their members' details.

        Returns:
            List of dictionaries with group and member information.
            Example: [{
                'name': 'Group1',
                'dn': 'CN=Group1,...',
                'members': [{
                    'name': 'User1',
                    'username': 'user1',
                    'email': 'user1@example.com',
                    'dn': 'CN=User1,...'
                }]
            }]
        """
        search_base = "OU=Mattermost,OU=Access,OU=Groups,OU=Saber3D,DC=SABER3D,DC=NET"

        group_entries = self._search(
            "(objectClass=group)", ["cn", "distinguishedName", "member"], search_base
        )

        groups = []
        for group_entry in group_entries:
            group_data = {
                "name": group_entry.cn.value,
                "dn": group_entry.distinguishedName.value,
                "members": [],
            }

            if hasattr(group_entry, "member") and group_entry.member:
                for member_dn in group_entry.member.values:
                    try:
                        user_entries = self._search(
                            "(objectClass=user)",
                            ["cn", "sAMAccountName", "mail"],
                            member_dn,
                            ldap3.BASE,
                        )

                        if user_entries:
                            member = user_entries[0]
                            group_data["members"].append(
                                {
                                    "name": (member.cn.value if hasattr(member, "cn") else None),
                                    "username": (
                                        member.sAMAccountName.value
                                        if hasattr(member, "sAMAccountName")
                                        else None
                                    ),
                                    "email": (
                                        member.mail.value if hasattr(member, "mail") else None
                                    ),
                                    "dn": member_dn,
                                }
                            )
                    except Exception as e:
                        print(f"Failed to get details for member {member_dn}: {str(e)}")
                        continue

            groups.append(group_data)

        return groups

    def close(self) -> None:
        """Close LDAP connection."""
        if self.connection:
            try:
                self.connection.unbind()
            except Exception as e:
                raise LDAPConnectionError(f"Failed to close LDAP connection: {e}") from e
            finally:
                self.connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
