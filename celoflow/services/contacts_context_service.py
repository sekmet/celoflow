"""
Contacts Context Service - Provides contacts information to the agent.

This service automatically detects and provides contacts context to the agent
so it can suggest recipients and provide personalized remittance recommendations.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ContactInfo:
    """Contact information data structure."""
    id: str
    name: str
    address: str
    network: str
    city: str
    country: str
    avatar: str
    phone: str
    email: str
    notes: str
    favorite: bool
    blocked: bool
    group: str
    created_at: str
    updated_at: str


class ContactsContextService:
    """Service for managing contacts context and providing it to the agent."""
    
    def __init__(self):
        self._contacts: List[ContactInfo] = []
    
    async def update_contacts(self, contacts_data: List[Dict[str, Any]]) -> None:
        """Update contacts context from frontend data."""
        try:
            self._contacts = [
                ContactInfo(
                    id=contact.get("id", ""),
                    name=contact.get("name", ""),
                    address=contact.get("address", ""),
                    network=contact.get("network", ""),
                    city=contact.get("city", ""),
                    country=contact.get("country", ""),
                    avatar=contact.get("avatar", ""),
                    phone=contact.get("phone", ""),
                    email=contact.get("email", ""),
                    notes=contact.get("notes", ""),
                    favorite=contact.get("favorite", False),
                    blocked=contact.get("blocked", False),
                    group=contact.get("group", ""),
                    created_at=contact.get("createdAt", ""),
                    updated_at=contact.get("updatedAt", "")
                )
                for contact in contacts_data
            ]
            logger.info(f"Updated contacts context with {len(self._contacts)} contacts")
        except Exception as e:
            logger.error(f"Failed to update contacts context: {e}")
            self._contacts = []
    
    def get_contacts(self) -> List[ContactInfo]:
        """Get all contacts."""
        return self._contacts
    
    def get_contacts_string(self) -> str:
        """Get contacts context as a formatted string for the agent."""
        if not self._contacts:
            return "No contacts available. User needs to add contacts first."
        
        # Filter out blocked contacts
        active_contacts = [c for c in self._contacts if not c.blocked]
        
        if not active_contacts:
            return "No active contacts available. All contacts are blocked."
        
        context_lines = [
            f"Contacts Status: {len(active_contacts)} active contacts available",
            f"Favorite Contacts: {len([c for c in active_contacts if c.favorite])}",
            f"Groups: {sorted(set(c.group for c in active_contacts if c.group))}",
            "",
            "Available Contacts:"
        ]
        
        # Sort by favorites first, then by updated_at
        sorted_contacts = sorted(
            active_contacts,
            key=lambda c: (not c.favorite, c.updated_at),
            reverse=True
        )
        
        for contact in sorted_contacts[:10]:  # Show top 10 contacts
            favorite_mark = "⭐" if contact.favorite else ""
            group_info = f" ({contact.group})" if contact.group else ""
            context_lines.append(
                f"- {favorite_mark}{contact.name}{group_info} - {contact.city}, {contact.country}"
            )
            context_lines.append(f"  Address: {contact.address}")
            if contact.notes:
                context_lines.append(f"  Notes: {contact.notes}")
        
        if len(active_contacts) > 10:
            context_lines.append(f"... and {len(active_contacts) - 10} more contacts")
        
        return "\n".join(context_lines)
    
    def get_contacts_by_country(self, country: str) -> List[ContactInfo]:
        """Get contacts filtered by country."""
        return [c for c in self._contacts if c.country.lower() == country.lower() and not c.blocked]
    
    def get_contacts_by_group(self, group: str) -> List[ContactInfo]:
        """Get contacts filtered by group."""
        return [c for c in self._contacts if c.group.lower() == group.lower() and not c.blocked]
    
    def get_favorite_contacts(self) -> List[ContactInfo]:
        """Get favorite contacts."""
        return [c for c in self._contacts if c.favorite and not c.blocked]
    
    def get_recent_contacts(self, limit: int = 5) -> List[ContactInfo]:
        """Get recently updated contacts."""
        return sorted(
            [c for c in self._contacts if not c.blocked],
            key=lambda c: c.updated_at,
            reverse=True
        )[:limit]
    
    def search_contacts(self, query: str) -> List[ContactInfo]:
        """Search contacts by name, email, or notes."""
        query_lower = query.lower()
        return [
            c for c in self._contacts 
            if not c.blocked and (
                query_lower in c.name.lower() or
                query_lower in c.email.lower() or
                query_lower in c.notes.lower() or
                query_lower in c.city.lower() or
                query_lower in c.country.lower()
            )
        ]
    
    def suggest_contacts_for_destination(self, destination: str) -> List[ContactInfo]:
        """Suggest contacts for a specific destination."""
        # Try to find contacts by country
        country_contacts = self.get_contacts_by_country(destination)
        if country_contacts:
            # Prioritize favorites
            favorites = [c for c in country_contacts if c.favorite]
            others = [c for c in country_contacts if not c.favorite]
            return favorites + others
        
        # If no country matches, search in city/notes
        return self.search_contacts(destination)
    
    def has_contacts(self) -> bool:
        """Check if user has any contacts."""
        return len([c for c in self._contacts if not c.blocked]) > 0


# Global instance for the service
contacts_context_service = ContactsContextService()
