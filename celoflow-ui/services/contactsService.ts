import { Contact } from '../types';

const STORAGE_KEY = 'celoflow_contacts';

function generateId(): string {
  return `contact_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function loadContacts(): Contact[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveContacts(contacts: Contact[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(contacts));
}

export function getContacts(): Contact[] {
  return loadContacts();
}

export function getContact(id: string): Contact | undefined {
  return loadContacts().find((c) => c.id === id);
}

export function createContact(data: Omit<Contact, 'id' | 'createdAt' | 'updatedAt'>): Contact {
  const contacts = loadContacts();
  const now = new Date().toISOString();
  const contact: Contact = {
    ...data,
    id: generateId(),
    createdAt: now,
    updatedAt: now,
  };
  contacts.push(contact);
  saveContacts(contacts);
  return contact;
}

export function updateContact(id: string, data: Partial<Omit<Contact, 'id' | 'createdAt'>>): Contact | null {
  const contacts = loadContacts();
  const idx = contacts.findIndex((c) => c.id === id);
  if (idx === -1) return null;
  contacts[idx] = {
    ...contacts[idx],
    ...data,
    updatedAt: new Date().toISOString(),
  };
  saveContacts(contacts);
  return contacts[idx];
}

export function deleteContact(id: string): boolean {
  const contacts = loadContacts();
  const filtered = contacts.filter((c) => c.id !== id);
  if (filtered.length === contacts.length) return false;
  saveContacts(filtered);
  return true;
}

export function toggleFavorite(id: string): Contact | null {
  const contacts = loadContacts();
  const idx = contacts.findIndex((c) => c.id === id);
  if (idx === -1) return null;
  contacts[idx].favorite = !contacts[idx].favorite;
  contacts[idx].updatedAt = new Date().toISOString();
  saveContacts(contacts);
  return contacts[idx];
}

export function toggleBlocked(id: string): Contact | null {
  const contacts = loadContacts();
  const idx = contacts.findIndex((c) => c.id === id);
  if (idx === -1) return null;
  contacts[idx].blocked = !contacts[idx].blocked;
  contacts[idx].updatedAt = new Date().toISOString();
  saveContacts(contacts);
  return contacts[idx];
}

export type SortField = 'name' | 'address' | 'country' | 'createdAt';
export type SortDirection = 'asc' | 'desc';
export type FilterMode = 'all' | 'favorites' | 'blocked';

export function searchContacts(
  query: string,
  filter: FilterMode = 'all',
  sortBy: SortField = 'name',
  sortDir: SortDirection = 'asc',
  group?: string,
): Contact[] {
  let contacts = loadContacts();
  const q = query.toLowerCase().trim();

  if (q) {
    contacts = contacts.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.address.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        c.phone.includes(q) ||
        c.country.toLowerCase().includes(q) ||
        c.city.toLowerCase().includes(q),
    );
  }

  if (filter === 'favorites') contacts = contacts.filter((c) => c.favorite);
  if (filter === 'blocked') contacts = contacts.filter((c) => c.blocked);
  if (group) contacts = contacts.filter((c) => c.group === group);

  contacts.sort((a, b) => {
    const aVal = a[sortBy] ?? '';
    const bVal = b[sortBy] ?? '';
    const cmp = String(aVal).localeCompare(String(bVal));
    return sortDir === 'asc' ? cmp : -cmp;
  });

  return contacts;
}

export function exportContacts(contacts: Contact[]): string {
  return JSON.stringify(contacts, null, 2);
}

export function importContacts(jsonString: string): { imported: number; errors: number } {
  try {
    const parsed = JSON.parse(jsonString);
    if (!Array.isArray(parsed)) return { imported: 0, errors: 1 };

    const existing = loadContacts();
    const existingAddresses = new Set(existing.map((c) => c.address.toLowerCase()));
    let imported = 0;
    let errors = 0;

    for (const item of parsed) {
      if (!item.name || !item.address) {
        errors++;
        continue;
      }
      if (existingAddresses.has(item.address.toLowerCase())) {
        errors++;
        continue;
      }
      const now = new Date().toISOString();
      existing.push({
        id: generateId(),
        name: item.name || '',
        address: item.address || '',
        network: item.network || 'celo',
        city: item.city || '',
        country: item.country || '',
        avatar: item.avatar || '',
        phone: item.phone || '',
        email: item.email || '',
        notes: item.notes || '',
        favorite: item.favorite || false,
        blocked: item.blocked || false,
        group: item.group || '',
        createdAt: now,
        updatedAt: now,
      });
      imported++;
    }

    saveContacts(existing);
    return { imported, errors };
  } catch {
    return { imported: 0, errors: 1 };
  }
}

export function getGroups(): string[] {
  const contacts = loadContacts();
  const groups = new Set(contacts.map((c) => c.group).filter(Boolean));
  return Array.from(groups).sort();
}

export function shareContactsAsText(contacts: Contact[]): string {
  return contacts
    .map(
      (c) =>
        `${c.name} | ${c.address} | ${c.network} | ${c.phone} | ${c.email} | ${c.city}, ${c.country}`,
    )
    .join('\n');
}
