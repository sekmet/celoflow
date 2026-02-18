import { createRxDatabase } from 'rxdb/plugins/core';
import { getRxStorageDexie } from 'rxdb/plugins/storage-dexie';
import { wrappedValidateZSchemaStorage } from 'rxdb/plugins/validate-z-schema';
import { addRxPlugin } from 'rxdb';
import { RxDBDevModePlugin } from 'rxdb/plugins/dev-mode';
import type { RxCollection, RxDatabase, RxJsonSchema } from 'rxdb';
import { Contact } from '../types';

// Enable dev-mode for detailed error messages in development
if (import.meta.env.DEV) {
  addRxPlugin(RxDBDevModePlugin);
}

interface ContactsCollections {
  contacts: RxCollection<Contact>;
}

const DATABASE_NAME = 'celoflow_contacts_db_v2';
const COLLECTION_NAME = 'contacts';

const contactSchema: RxJsonSchema<Contact> = {
  title: 'celoflow contacts schema',
  description: 'Stores user contacts for CeloFlow UI',
  version: 0,
  keyCompression: false,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: { type: 'string', maxLength: 128 },
    name: { type: 'string', maxLength: 256 },
    address: { type: 'string', maxLength: 256 },
    network: { type: 'string', maxLength: 64 },
    city: { type: 'string', maxLength: 128 },
    country: { type: 'string', maxLength: 128 },
    avatar: { type: 'string', maxLength: 512 },
    phone: { type: 'string', maxLength: 32 },
    email: { type: 'string', maxLength: 256 },
    notes: { type: 'string', maxLength: 1024 },
    favorite: { type: 'boolean' },
    blocked: { type: 'boolean' },
    group: { type: 'string', maxLength: 128 },
    createdAt: { type: 'string', maxLength: 64 },
    updatedAt: { type: 'string', maxLength: 64 },
  },
  required: [
    'id',
    'name',
    'address',
    'network',
    'city',
    'country',
    'avatar',
    'phone',
    'email',
    'notes',
    'favorite',
    'blocked',
    'group',
    'createdAt',
    'updatedAt',
  ],
  indexes: ['name', 'address', 'country', 'createdAt', 'group'],
};

let databasePromise: Promise<RxDatabase<ContactsCollections>> | null = null;
let collectionPromise: Promise<RxCollection<Contact>> | null = null;

function generateId(): string {
  return `contact_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// Fallback localStorage functions for when RxDB fails
function getLocalStorageContacts(): Contact[] {
  try {
    const stored = localStorage.getItem('celoflow_contacts');
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function setLocalStorageContacts(contacts: Contact[]): void {
  try {
    localStorage.setItem('celoflow_contacts', JSON.stringify(contacts));
  } catch (error) {
    console.error('Failed to save contacts to localStorage:', error);
  }
}

async function getDatabase(): Promise<RxDatabase<ContactsCollections>> {
  if (!databasePromise) {
    databasePromise = (async () => {
      try {
        const db = await createRxDatabase<ContactsCollections>({
          name: DATABASE_NAME,
          storage: wrappedValidateZSchemaStorage({ storage: getRxStorageDexie() }),
          multiInstance: false,
        });
        return db;
      } catch (error) {
        console.error('Failed to create RxDB database:', error);
        // Reset promise to allow retry
        databasePromise = null;
        throw error;
      }
    })();
  }

  return databasePromise;
}

async function getContactsCollection(): Promise<RxCollection<Contact>> {
  if (!collectionPromise) {
    collectionPromise = (async () => {
      try {
        const db = await getDatabase();
        if (db.collections[COLLECTION_NAME]) return db.collections[COLLECTION_NAME] as RxCollection<Contact>;

        await db.addCollections({
          contacts: {
            schema: contactSchema,
          },
        });

        return db.collections[COLLECTION_NAME] as RxCollection<Contact>;
      } catch (error) {
        console.error('Failed to get or create contacts collection:', error);
        // Reset promise to allow retry
        collectionPromise = null;
        throw error;
      }
    })();
  }

  return collectionPromise;
}

async function getContactDocument(id: string) {
  const collection = await getContactsCollection();
  return collection.findOne(id).exec();
}

export async function getContacts(): Promise<Contact[]> {
  try {
    const collection = await getContactsCollection();
    const docs = await collection.find().exec();
    return docs.map((doc) => doc.toJSON());
  } catch (error) {
    console.warn('RxDB failed, falling back to localStorage:', error);
    return getLocalStorageContacts();
  }
}

export async function getContact(id: string): Promise<Contact | undefined> {
  const document = await getContactDocument(id);
  return document ? document.toJSON() : undefined;
}

export async function createContact(data: Omit<Contact, 'id' | 'createdAt' | 'updatedAt'>): Promise<Contact> {
  try {
    const collection = await getContactsCollection();
    const now = new Date().toISOString();
    const contact: Contact = {
      ...data,
      id: generateId(),
      createdAt: now,
      updatedAt: now,
    };
    await collection.insert(contact);
    return contact;
  } catch (error) {
    console.warn('RxDB failed, using localStorage fallback:', error);
    const now = new Date().toISOString();
    const contact: Contact = {
      ...data,
      id: generateId(),
      createdAt: now,
      updatedAt: now,
    };
    const contacts = getLocalStorageContacts();
    contacts.push(contact);
    setLocalStorageContacts(contacts);
    return contact;
  }
}

export async function updateContact(
  id: string,
  data: Partial<Omit<Contact, 'id' | 'createdAt'>>,
): Promise<Contact | null> {
  const collection = await getContactsCollection();
  const current = await getContactDocument(id);
  if (!current) return null;

  const updated: Contact = {
    ...current.toJSON(),
    ...data,
    updatedAt: new Date().toISOString(),
  };

  await collection.upsert(updated);
  return updated;
}

export async function deleteContact(id: string): Promise<boolean> {
  const document = await getContactDocument(id);
  if (!document) return false;

  await document.remove();
  return true;
}

export async function toggleFavorite(id: string): Promise<Contact | null> {
  const contact = await getContact(id);
  if (!contact) return null;

  return updateContact(id, { favorite: !contact.favorite });
}

export async function toggleBlocked(id: string): Promise<Contact | null> {
  const contact = await getContact(id);
  if (!contact) return null;

  return updateContact(id, { blocked: !contact.blocked });
}

export type SortField = 'name' | 'address' | 'country' | 'createdAt';
export type SortDirection = 'asc' | 'desc';
export type FilterMode = 'all' | 'favorites' | 'blocked';

export async function searchContacts(
  query: string,
  filter: FilterMode = 'all',
  sortBy: SortField = 'name',
  sortDir: SortDirection = 'asc',
  group?: string,
): Promise<Contact[]> {
  let contacts = await getContacts();
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

export async function importContacts(jsonString: string): Promise<{ imported: number; errors: number }> {
  try {
    const parsed = JSON.parse(jsonString);
    if (!Array.isArray(parsed)) return { imported: 0, errors: 1 };

    const existing = await getContacts();
    const existingAddresses = new Set(existing.map((c) => c.address.toLowerCase()));
    let imported = 0;
    let errors = 0;

    const contactsToInsert: Contact[] = [];

    for (const item of parsed) {
      if (!item.name || !item.address) {
        errors++;
        continue;
      }
      if (existingAddresses.has(item.address.toLowerCase())) {
        errors++;
        continue;
      }

      existingAddresses.add(item.address.toLowerCase());
      const now = new Date().toISOString();
      contactsToInsert.push({
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

    if (contactsToInsert.length > 0) {
      const collection = await getContactsCollection();
      await collection.bulkInsert(contactsToInsert);
    }

    return { imported, errors };
  } catch {
    return { imported: 0, errors: 1 };
  }
}

export async function getGroups(): Promise<string[]> {
  const contacts = await getContacts();
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
