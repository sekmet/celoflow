import React, { useState, useEffect, useRef } from 'react';
import {
  Users, Plus, Search, Star, Ban, Edit3, Trash2, X, Download, Upload,
  Share2, ChevronDown, Filter, ArrowUpDown, UserPlus, Heart, Globe,
  Phone, Mail, MapPin, FileText, Check, AlertCircle, Copy,
} from 'lucide-react';
import { Contact } from '../types';
import {
  getContacts, createContact, updateContact, deleteContact,
  toggleFavorite, toggleBlocked, searchContacts, exportContacts,
  importContacts, getGroups, shareContactsAsText,
  type SortField, type SortDirection, type FilterMode,
} from '../services/contactsService';
import { useI18n } from '../lib/language';

interface ContactsManagerProps {
  onClose: () => void;
  onSelectContact?: (contact: Contact) => void;
}

const EMPTY_FORM: Omit<Contact, 'id' | 'createdAt' | 'updatedAt'> = {
  name: '', address: '', network: 'celo', city: '', country: '',
  avatar: '', phone: '', email: '', notes: '',
  favorite: false, blocked: false, group: '',
};

const NETWORKS = ['celo', 'ethereum', 'polygon', 'arbitrum', 'optimism', 'base'];

export const ContactsManager: React.FC<ContactsManagerProps> = ({ onClose, onSelectContact }) => {
  const { t } = useI18n();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<FilterMode>('all');
  const [sortBy, setSortBy] = useState<SortField>('name');
  const [sortDir, setSortDir] = useState<SortDirection>('asc');
  const [groupFilter, setGroupFilter] = useState('');
  const [groups, setGroups] = useState<string[]>([]);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const [showSortMenu, setShowSortMenu] = useState(false);
  const [showFilterMenu, setShowFilterMenu] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    const [results, nextGroups] = await Promise.all([
      searchContacts(query, filter, sortBy, sortDir, groupFilter || undefined),
      getGroups(),
    ]);
    setContacts(results);
    setGroups(nextGroups);
  };

  useEffect(() => {
    void refresh();
  }, [query, filter, sortBy, sortDir, groupFilter]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = t('Name is required');
    if (!form.address.trim()) errors.address = t('Address is required');
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      errors.email = t('Invalid email format');
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) return;
    if (editingId) {
      await updateContact(editingId, form);
      showToast(t('Contact updated'));
    } else {
      await createContact(form);
      showToast(t('Contact created'));
    }
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormErrors({});
    await refresh();
  };

  const handleEdit = (contact: Contact) => {
    setEditingId(contact.id);
    setForm({
      name: contact.name, address: contact.address, network: contact.network,
      city: contact.city, country: contact.country, avatar: contact.avatar,
      phone: contact.phone, email: contact.email, notes: contact.notes,
      favorite: contact.favorite, blocked: contact.blocked, group: contact.group,
    });
    setFormErrors({});
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    await deleteContact(id);
    setConfirmDelete(null);
    showToast(t('Contact deleted'));
    await refresh();
  };

  const handleToggleFavorite = async (id: string) => {
    await toggleFavorite(id);
    await refresh();
  };

  const handleToggleBlocked = async (id: string) => {
    await toggleBlocked(id);
    await refresh();
  };

  const handleExport = async () => {
    const allContacts = await getContacts();
    const json = exportContacts(allContacts);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `celoflow-contacts-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(t('Exported {{count}} contacts', { count: allContacts.length }));
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      const text = typeof ev.target?.result === 'string' ? ev.target.result : '';
      if (!text) {
        showToast(t('Import failed'));
        return;
      }

      const result = await importContacts(text);
      const importedText = t('Imported {{count}} contacts', { count: result.imported });
      const skippedText = result.errors
        ? t(', {{count}} skipped', { count: result.errors })
        : '';
      showToast(`${importedText}${skippedText}`);
      await refresh();
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleShare = async () => {
    const allContacts = await getContacts();
    if (allContacts.length === 0) {
      showToast(t('No contacts to share'));
      return;
    }
    const text = shareContactsAsText(allContacts);
    try {
      if (navigator.share) {
        await navigator.share({ title: t('CeloFlow Contacts'), text });
      } else {
        await navigator.clipboard.writeText(text);
        showToast(t('Contacts copied to clipboard'));
      }
    } catch {
      showToast(t('Share failed'));
    }
  };

  const handleCopyAddress = async (address: string) => {
    await navigator.clipboard.writeText(address);
    showToast(t('Address copied'));
  };

  const getInitials = (name: string) => {
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2) || '??';
  };

  const getAvatarColor = (name: string) => {
    const colors = [
      'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500',
      'bg-pink-500', 'bg-teal-500', 'bg-indigo-500', 'bg-red-500',
    ];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl max-h-[90vh] bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden animate-fade-in-up">

        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <Users className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h2 className="font-bold text-gray-900 dark:text-white text-lg">{t('Contacts')}</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {contacts.length === 1
                  ? t('{{count}} contact', { count: contacts.length })
                  : t('{{count}} contacts', { count: contacts.length })}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => { setShowForm(true); setEditingId(null); setForm(EMPTY_FORM); setFormErrors({}); }}
              className="p-2 bg-celo-green text-white rounded-lg hover:bg-green-500 transition-colors" title={t('Add Contact')}>
              <Plus className="w-4 h-4" />
            </button>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="px-6 py-3 border-b border-gray-100 dark:border-gray-700 flex flex-wrap gap-2 items-center shrink-0">
          <div className="flex-1 min-w-[200px] relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
            <input type="text" placeholder={t('Search contacts...')} value={query} onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green placeholder-gray-500 dark:placeholder-gray-400" />
          </div>

          {/* Filter dropdown */}
          <div className="relative">
            <button onClick={() => { setShowFilterMenu(!showFilterMenu); setShowSortMenu(false); }}
              className={`flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${filter !== 'all' ? 'bg-celo-green text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}`}>
              <Filter className="w-3 h-3" /> {filter === 'all' ? t('All') : filter === 'favorites' ? t('Favorites') : t('Blocked')}
              <ChevronDown className="w-3 h-3" />
            </button>
            {showFilterMenu && (
              <div className="absolute right-0 top-full mt-1 w-36 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 z-50 overflow-hidden">
                {(['all', 'favorites', 'blocked'] as FilterMode[]).map((f) => (
                  <button key={f} onClick={() => { setFilter(f); setShowFilterMenu(false); }}
                    className={`w-full text-left px-4 py-2 text-sm capitalize hover:bg-gray-50 dark:hover:bg-gray-700 ${filter === f ? 'text-celo-green font-bold' : 'text-gray-700 dark:text-gray-300'}`}>
                    {f === 'all' ? t('All') : f === 'favorites' ? t('Favorites') : t('Blocked')}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Sort dropdown */}
          <div className="relative">
            <button onClick={() => { setShowSortMenu(!showSortMenu); setShowFilterMenu(false); }}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
              <ArrowUpDown className="w-3 h-3" /> {t('Sort')}
            </button>
            {showSortMenu && (
              <div className="absolute right-0 top-full mt-1 w-44 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 z-50 overflow-hidden">
                {([['name', 'Name'], ['address', 'Address'], ['country', 'Country'], ['createdAt', 'Date Added']] as [SortField, string][]).map(([field, label]) => (
                  <button key={field} onClick={() => {
                    if (sortBy === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
                    else { setSortBy(field); setSortDir('asc'); }
                    setShowSortMenu(false);
                  }}
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex justify-between ${sortBy === field ? 'text-celo-green font-bold' : 'text-gray-700 dark:text-gray-300'}`}>
                    {t(label)}
                    {sortBy === field && <span className="text-xs">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Group filter */}
          {groups.length > 0 && (
            <select value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}
              className="px-3 py-2 rounded-lg text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 outline-none">
              <option value="">{t('All Groups')}</option>
              {groups.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          )}

          {/* Actions */}
          <div className="flex gap-1 ml-auto">
            <button onClick={handleExport} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title={t('Export')}>
              <Download className="w-4 h-4 text-gray-500" />
            </button>
            <button onClick={() => fileInputRef.current?.click()} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title={t('Import')}>
              <Upload className="w-4 h-4 text-gray-500" />
            </button>
            <button onClick={handleShare} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title={t('Share')}>
              <Share2 className="w-4 h-4 text-gray-500" />
            </button>
            <input ref={fileInputRef} type="file" accept=".json" onChange={handleImport} className="hidden" />
          </div>
        </div>

        {/* Contact List */}
        <div className="flex-1 overflow-y-auto">
          {contacts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <UserPlus className="w-12 h-12 mb-3 opacity-50" />
              <p className="text-sm font-medium">{query ? t('No matching contacts') : t('No contacts yet')}</p>
              <p className="text-xs mt-1">{t('Click + to add your first contact')}</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {contacts.map((contact) => (
                <div key={contact.id}
                  className={`px-6 py-3 flex items-center gap-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors group ${contact.blocked ? 'opacity-60' : ''}`}>

                  {/* Avatar */}
                  <div className={`w-10 h-10 rounded-full ${contact.avatar ? '' : getAvatarColor(contact.name)} flex items-center justify-center text-white text-sm font-bold shrink-0 relative`}>
                    {contact.avatar ? (
                      <img src={contact.avatar} alt={contact.name} className="w-full h-full rounded-full object-cover" />
                    ) : (
                      getInitials(contact.name)
                    )}
                    {contact.favorite && (
                      <div className="absolute -top-1 -right-1 w-4 h-4 bg-yellow-400 rounded-full flex items-center justify-center">
                        <Star className="w-2.5 h-2.5 text-white fill-white" />
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => onSelectContact?.(contact)}>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-gray-900 dark:text-white truncate">{contact.name}</span>
                      {contact.blocked && <Ban className="w-3 h-3 text-red-500 shrink-0" />}
                      {contact.group && (
                        <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-600 rounded text-[10px] text-gray-500 dark:text-gray-400">{contact.group}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      <span className="font-mono truncate max-w-[180px]">{contact.address.slice(0, 8)}...{contact.address.slice(-6)}</span>
                      <span className="px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px] uppercase">{contact.network}</span>
                      {contact.country && (
                        <span className="flex items-center gap-0.5"><MapPin className="w-3 h-3" />{contact.city ? `${contact.city}, ` : ''}{contact.country}</span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button onClick={() => handleCopyAddress(contact.address)}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors" title={t('Copy address')}>
                      <Copy className="w-3.5 h-3.5 text-gray-400" />
                    </button>
                    <button onClick={() => handleToggleFavorite(contact.id)}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors" title={t('Toggle favorite')}>
                      <Star className={`w-3.5 h-3.5 ${contact.favorite ? 'text-yellow-500 fill-yellow-500' : 'text-gray-400'}`} />
                    </button>
                    <button onClick={() => handleToggleBlocked(contact.id)}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors" title={t('Toggle blocked')}>
                      <Ban className={`w-3.5 h-3.5 ${contact.blocked ? 'text-red-500' : 'text-gray-400'}`} />
                    </button>
                    <button onClick={() => handleEdit(contact)}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors" title={t('Edit')}>
                      <Edit3 className="w-3.5 h-3.5 text-gray-400" />
                    </button>
                    <button onClick={() => setConfirmDelete(contact.id)}
                      className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg transition-colors" title={t('Delete')}>
                      <Trash2 className="w-3.5 h-3.5 text-red-400" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Toast */}
        {toast && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 px-4 py-2 rounded-full text-sm font-medium shadow-lg flex items-center gap-2 animate-fade-in-up z-50">
            <Check className="w-4 h-4" /> {toast}
          </div>
        )}

        {/* Delete Confirmation */}
        {confirmDelete && (
          <div className="absolute inset-0 bg-black/30 flex items-center justify-center z-50 rounded-2xl">
            <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-xl border border-gray-200 dark:border-gray-700 max-w-sm mx-4">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                  <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <h3 className="font-bold text-gray-900 dark:text-white">{t('Delete Contact')}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t('This action cannot be undone.')}</p>
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setConfirmDelete(null)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
                  {t('Cancel')}
                </button>
                <button onClick={() => handleDelete(confirmDelete)}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors">
                  {t('Delete')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add/Edit Form Modal */}
        {showForm && (
          <div className="absolute inset-0 bg-white dark:bg-gray-800 z-40 flex flex-col rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between shrink-0">
              <h3 className="font-bold text-gray-900 dark:text-white text-lg">
                {editingId ? t('Edit Contact') : t('New Contact')}
              </h3>
              <button onClick={() => { setShowForm(false); setEditingId(null); setForm(EMPTY_FORM); setFormErrors({}); }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">{t('Name')} *</label>
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className={`w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border ${formErrors.name ? 'border-red-400' : 'border-gray-200 dark:border-gray-600'} text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green`}
                  placeholder={t('John Doe')} />
                {formErrors.name && <p className="text-xs text-red-500 mt-1">{formErrors.name}</p>}
              </div>

              {/* Address + Network */}
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">{t('Wallet Address')} *</label>
                  <input type="text" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}
                    className={`w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border ${formErrors.address ? 'border-red-400' : 'border-gray-200 dark:border-gray-600'} text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green font-mono`}
                    placeholder={t('0x...')} />
                  {formErrors.address && <p className="text-xs text-red-500 mt-1">{formErrors.address}</p>}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">{t('Network')}</label>
                  <select value={form.network} onChange={(e) => setForm({ ...form, network: e.target.value })}
                    className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green">
                    {NETWORKS.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
              </div>

              {/* Phone + Email */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><Phone className="w-3 h-3" /> {t('Phone')}</label>
                  <input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green"
                    placeholder={t('+1 234 567 8900')} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><Mail className="w-3 h-3" /> {t('Email')}</label>
                  <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className={`w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border ${formErrors.email ? 'border-red-400' : 'border-gray-200 dark:border-gray-600'} text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green`}
                    placeholder={t('john@example.com')} />
                  {formErrors.email && <p className="text-xs text-red-500 mt-1">{formErrors.email}</p>}
                </div>
              </div>

              {/* City + Country */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><MapPin className="w-3 h-3" /> {t('City')}</label>
                  <input type="text" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })}
                    className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green"
                    placeholder={t('Manila')} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><Globe className="w-3 h-3" /> {t('Country')}</label>
                  <input type="text" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })}
                    className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green"
                    placeholder={t('Philippines')} />
                </div>
              </div>

              {/* Avatar URL + Group */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">{t('Avatar URL')}</label>
                  <input type="url" value={form.avatar} onChange={(e) => setForm({ ...form, avatar: e.target.value })}
                    className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green"
                    placeholder={t('https://...')} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">{t('Group')}</label>
                  <input type="text" value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })}
                    className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green"
                    placeholder={t('Family, Work, etc.')} list="group-suggestions" />
                  <datalist id="group-suggestions">
                    {groups.map((g) => <option key={g} value={g} />)}
                  </datalist>
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><FileText className="w-3 h-3" /> {t('Notes')}</label>
                <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green resize-none"
                  placeholder={t('Additional notes...')} />
              </div>

              {/* Flags */}
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.favorite} onChange={(e) => setForm({ ...form, favorite: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300 text-yellow-500 focus:ring-yellow-500" />
                  <Star className="w-4 h-4 text-yellow-500" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">{t('Favorite')}</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.blocked} onChange={(e) => setForm({ ...form, blocked: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300 text-red-500 focus:ring-red-500" />
                  <Ban className="w-4 h-4 text-red-500" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">{t('Blocked')}</span>
                </label>
              </div>
            </div>

            {/* Form Actions */}
            <div className="px-6 py-4 border-t border-gray-100 dark:border-gray-700 flex gap-3 justify-end shrink-0">
              <button onClick={() => { setShowForm(false); setEditingId(null); setForm(EMPTY_FORM); setFormErrors({}); }}
                className="px-6 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
                {t('Cancel')}
              </button>
              <button onClick={handleSave}
                className="px-6 py-2.5 text-sm font-medium text-white bg-celo-green rounded-lg hover:bg-green-500 transition-colors flex items-center gap-2">
                <Check className="w-4 h-4" />
                {editingId ? t('Update') : t('Create')}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
