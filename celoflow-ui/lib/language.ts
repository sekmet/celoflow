import { useEffect, useState } from 'react';

export type SupportedLanguage = 'en' | 'es' | 'pt' | 'fr' | 'de' | 'it';

export interface LanguageOption {
  code: SupportedLanguage;
  name: string;
  nativeName: string;
  flag: string;
}

function interpolate(template: string, params?: TranslationParams): string {
  if (!params) return template;

  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (_match, key) => {
    const value = params[key];
    return value === undefined ? '' : String(value);
  });
}

export function translate(language: SupportedLanguage, text: string, params?: TranslationParams): string {
  const translated = TRANSLATIONS[language][text] ?? text;
  return interpolate(translated, params);
}

export const LANGUAGE_OPTIONS: LanguageOption[] = [
  { code: 'en', name: 'English', nativeName: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Spanish', nativeName: 'Espanol', flag: '🇪🇸' },
  { code: 'pt', name: 'Portuguese', nativeName: 'Portugues', flag: '🇧🇷' },
  { code: 'fr', name: 'French', nativeName: 'Francais', flag: '🇫🇷' },
  { code: 'de', name: 'German', nativeName: 'Deutsch', flag: '🇩🇪' },
  { code: 'it', name: 'Italian', nativeName: 'Italiano', flag: '🇮🇹' },
];

export const LANGUAGE_STORAGE_KEY = 'celoflow_language';
const LANGUAGE_EVENT = 'celoflow:language-change';

type TranslationMap = Record<string, string>;
export type TranslationParams = Record<string, string | number>;

const TRANSLATIONS: Record<SupportedLanguage, TranslationMap> = {
  en: {},
  es: {
    Language: 'Idioma',
    Contacts: 'Contactos',
    'How it Works': 'Como funciona',
    Features: 'Funciones',
    Developers: 'Desarrolladores',
    'Launch App': 'Abrir app',
    'SMART AGENT LIVE': 'AGENTE INTELIGENTE ACTIVO',
    'Send Money Like': 'Envia dinero como',
    'You Send a': 'si enviaras un',
    Message: 'mensaje',
    'The financial agent that turns your words into instant global transfers on the Celo blockchain. Simple, secure, and fast.':
      'El agente financiero que convierte tus palabras en transferencias globales instantaneas en la blockchain de Celo. Simple, seguro y rapido.',
    'Try CeloFlow Now': 'Probar CeloFlow',
    'View Activity': 'Ver actividad',
    'Trusted by 10,000+ early users': 'Con la confianza de 10,000+ usuarios tempranos',
    'Just Saved': 'Acabas de ahorrar',
    '$3.50 vs Bank': '$3.50 vs banco',
    'Built for the Real World': 'Disenado para el mundo real',
    'CeloFlow leverages advanced blockchain infrastructure to make money move as freely as information.':
      'CeloFlow aprovecha infraestructura blockchain avanzada para mover dinero tan libremente como la informacion.',
    'Mento Protocol': 'Protocolo Mento',
    'Seamlessly swaps stablecoins (cUSD, cEUR, cREAL) with minimal slippage using decentralized stability mechanisms.':
      'Intercambia stablecoins (cUSD, cEUR, cREAL) con deslizamiento minimo mediante mecanismos de estabilidad descentralizados.',
    'TEE Security': 'Seguridad TEE',
    'Your keys are managed in a Trusted Execution Environment. You authenticate; the enclave signs. No seed phrases to lose.':
      'Tus claves se administran en un Entorno de Ejecucion Confiable. Tu autenticas, el enclave firma. Sin frases semilla.',
    'Gas Abstraction': 'Abstraccion de gas',
    'Pay transaction fees in the same currency you send. No need to hold CELO just to pay for gas.':
      'Paga comisiones en la misma moneda que envias. No necesitas CELO para pagar gas.',
    'Ready to ditch the bank fees?': 'Listo para dejar las comisiones bancarias?',
    'Join the thousands of users saving on every remittance with CeloFlow.':
      'Unete a miles de usuarios que ahorran en cada remesa con CeloFlow.',
    'Enter your email': 'Ingresa tu correo',
    'Get Early Access': 'Obtener acceso temprano',
    'Privacy Policy': 'Politica de privacidad',
    'Terms of Service': 'Terminos del servicio',
    Contact: 'Contacto',
    '© 2024 CeloFlow. Built on Celo.': '© 2024 CeloFlow. Construido en Celo.',
    Connected: 'Conectado',
    Unknown: 'Desconocido',
    Balance: 'Saldo',
    'Disconnect Wallet': 'Desconectar billetera',
    'Connect Wallet': 'Conectar billetera',
    'Connect a Wallet': 'Conectar una billetera',
    'Copy address': 'Copiar direccion',
    'Smart Agent v2.1': 'Agente Inteligente v2.1',
    'AI that thinks like a': 'IA que piensa como un',
    'Market Maker.': 'market maker.',
    'CeloFlow scans decentralized exchanges (DEXs) and the Mento Protocol in real-time to find liquidity pools with the lowest slippage, ensuring your family gets the most out of every dollar sent.':
      'CeloFlow analiza DEX y el Protocolo Mento en tiempo real para encontrar pools con menor deslizamiento y maximizar cada dolar enviado.',
    Slippage: 'Deslizamiento',
    'Route Time': 'Tiempo de ruta',
    'Avg. Savings': 'Ahorro prom.',
    'Route Optimization': 'Optimizacion de ruta',
    Active: 'Activo',
    Stablecoin: 'Stablecoin',
    Local: 'Local',
    'TEE Verification Complete': 'Verificacion TEE completada',
    'Key management is handled inside a secure enclave. You never touch a private key.':
      'La gestion de claves se realiza dentro de un enclave seguro. Nunca tocas una clave privada.',
    All: 'Todos',
    Favorites: 'Favoritos',
    Blocked: 'Bloqueado',
    Sort: 'Ordenar',
    Name: 'Nombre',
    Address: 'Direccion',
    Country: 'Pais',
    'Date Added': 'Fecha de alta',
    Export: 'Exportar',
    Import: 'Importar',
    Share: 'Compartir',
    'No matching contacts': 'No hay contactos coincidentes',
    'No contacts yet': 'Aun no hay contactos',
    'Click + to add your first contact': 'Haz clic en + para agregar tu primer contacto',
    'Toggle favorite': 'Alternar favorito',
    'Toggle blocked': 'Alternar bloqueo',
    Edit: 'Editar',
    Delete: 'Eliminar',
    'Delete Contact': 'Eliminar contacto',
    'This action cannot be undone.': 'Esta accion no se puede deshacer.',
    Cancel: 'Cancelar',
    'Edit Contact': 'Editar contacto',
    'New Contact': 'Nuevo contacto',
    'Name is required': 'El nombre es obligatorio',
    'Wallet Address': 'Direccion de wallet',
    'Address is required': 'La direccion es obligatoria',
    Network: 'Red',
    Phone: 'Telefono',
    Email: 'Correo',
    'Invalid email format': 'Formato de correo invalido',
    City: 'Ciudad',
    'Avatar URL': 'URL del avatar',
    Group: 'Grupo',
    Notes: 'Notas',
    Favorite: 'Favorito',
    Update: 'Actualizar',
    Create: 'Crear',
    'John Doe': 'Juan Perez',
    '0x...': '0x...',
    '+1 234 567 8900': '+34 600 000 000',
    'john@example.com': 'juan@ejemplo.com',
    Manila: 'Manila',
    Philippines: 'Filipinas',
    'https://...': 'https://...',
    'Family, Work, etc.': 'Familia, Trabajo, etc.',
    'Additional notes...': 'Notas adicionales...',
    'Contact updated': 'Contacto actualizado',
    'Contact created': 'Contacto creado',
    'Contact deleted': 'Contacto eliminado',
    'Exported {{count}} contacts': 'Se exportaron {{count}} contactos',
    'Import failed': 'Fallo la importacion',
    'Imported {{count}} contacts': 'Se importaron {{count}} contactos',
    ', {{count}} skipped': ', {{count}} omitidos',
    'No contacts to share': 'No hay contactos para compartir',
    'Contacts copied to clipboard': 'Contactos copiados al portapapeles',
    'Share failed': 'Error al compartir',
    'Address copied': 'Direccion copiada',
    '{{count}} contact': '{{count}} contacto',
    '{{count}} contacts': '{{count}} contactos',
    'Add Contact': 'Agregar contacto',
    'Search contacts...': 'Buscar contactos...',
    'All Groups': 'Todos los grupos',
    'CeloFlow Contacts': 'Contactos de CeloFlow',
    "Hi! I'm CeloFlow. I can help you send money globally using the Celo blockchain. Where would you like to send money today?":
      'Hola! Soy CeloFlow. Puedo ayudarte a enviar dinero globalmente con la blockchain de Celo. A donde quieres enviar dinero hoy?',
    'Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.':
      'La entrada por voz no es compatible con este navegador. Usa Chrome, Edge o Safari.',
    'Sorry, I encountered an error connecting to the server. Please try again.':
      'Lo siento, hubo un error al conectar con el servidor. Intentalo de nuevo.',
    'Are you sure you want to cancel this scheduled payment?': 'Seguro que deseas cancelar este pago programado?',
    'CeloFlow Transaction': 'Transaccion de CeloFlow',
    'I just sent {{amount}} {{currency}} to {{recipient}} via CeloFlow!':
      'Acabo de enviar {{amount}} {{currency}} a {{recipient}} con CeloFlow!',
    'Transaction details copied to clipboard!': 'Detalles de la transaccion copiados al portapapeles!',
    'Funds have successfully reached the recipient.': 'Los fondos llegaron correctamente al destinatario.',
    'Transaction is currently being confirmed on the blockchain.':
      'La transaccion se esta confirmando en la blockchain.',
    'Payment is set to execute at a future date.': 'El pago esta programado para ejecutarse luego.',
    'This transaction was cancelled by the user.': 'Esta transaccion fue cancelada por el usuario.',
    'Transaction could not be completed. Please try again.':
      'No se pudo completar la transaccion. Intentalo nuevamente.',
    Online: 'En linea',
    'Transaction History': 'Historial de transacciones',
    'Recent Activity': 'Actividad reciente',
    'Search recipient or currency...': 'Buscar destinatario o moneda...',
    'No transactions yet.': 'Aun no hay transacciones.',
    'No matching transactions.': 'No hay transacciones coincidentes.',
    'Cancel Scheduled Payment': 'Cancelar pago programado',
    Sent: 'Enviado',
    Received: 'Recibido',
    '{{frequency}} starting {{startDate}}': '{{frequency}} desde {{startDate}}',
    'Best Quote Found': 'Mejor cotizacion encontrada',
    'Saved ${{amount}}': 'Ahorraste ${{amount}}',
    'You Send': 'Tu envias',
    Receives: 'Recibe',
    'Live Real-time Rate': 'Tasa en tiempo real',
    'Estimated Fallback Rate': 'Tasa estimada de respaldo',
    'Payment Schedule': 'Programacion de pago',
    'One-time': 'Una vez',
    Daily: 'Diario',
    Weekly: 'Semanal',
    Monthly: 'Mensual',
    'Mento Protocol Status': 'Estado del Protocolo Mento',
    Optimal: 'Optimo',
    'Total Network Fees': 'Comisiones totales de red',
    'Mento Swap Fee': 'Comision de swap Mento',
    'Celo Gas Fee': 'Comision de gas Celo',
    'Secure Enclave (TEE)': 'Enclave seguro (TEE)',
    'Est. Arrival': 'Llegada estimada',
    '< 5 seconds': '< 5 segundos',
    Scheduled: 'Programado',
    'Schedule Payment': 'Programar pago',
    'Confirm Transfer': 'Confirmar transferencia',
    'Payment Scheduled!': 'Pago programado!',
    'Transaction Sent!': 'Transaccion enviada!',
    '{{amount}} {{currency}} will be sent to {{recipient}} {{frequency}} starting {{startDate}}.':
      '{{amount}} {{currency}} se enviaran a {{recipient}} {{frequency}} a partir de {{startDate}}.',
    '{{amount}} {{currency}} is on its way to {{recipient}}.':
      '{{amount}} {{currency}} van en camino a {{recipient}}.',
    'View on CeloScan': 'Ver en CeloScan',
    'Processing request...': 'Procesando solicitud...',
    'Speak to CeloFlow': 'Hablar con CeloFlow',
    'Listening...': 'Escuchando...',
    'Type a command...': 'Escribe un comando...',
  },
  pt: {
    Language: 'Idioma',
    Contacts: 'Contatos',
    'How it Works': 'Como funciona',
    Features: 'Recursos',
    Developers: 'Desenvolvedores',
    'Launch App': 'Abrir app',
    'SMART AGENT LIVE': 'AGENTE INTELIGENTE AO VIVO',
    'Send Money Like': 'Envie dinheiro como',
    'You Send a': 'se estivesse enviando uma',
    Message: 'mensagem',
    'The financial agent that turns your words into instant global transfers on the Celo blockchain. Simple, secure, and fast.':
      'O agente financeiro que transforma suas palavras em transferencias globais instantaneas na blockchain Celo. Simples, seguro e rapido.',
    'Try CeloFlow Now': 'Experimentar CeloFlow',
    'View Activity': 'Ver atividade',
    'Trusted by 10,000+ early users': 'Confiado por 10.000+ usuarios iniciais',
    'Just Saved': 'Acabou de economizar',
    '$3.50 vs Bank': '$3.50 vs banco',
    'Built for the Real World': 'Feito para o mundo real',
    'CeloFlow leverages advanced blockchain infrastructure to make money move as freely as information.':
      'CeloFlow usa infraestrutura blockchain avancada para mover dinheiro com a mesma liberdade da informacao.',
    'Mento Protocol': 'Protocolo Mento',
    'Seamlessly swaps stablecoins (cUSD, cEUR, cREAL) with minimal slippage using decentralized stability mechanisms.':
      'Troca stablecoins (cUSD, cEUR, cREAL) com baixo slippage usando mecanismos descentralizados de estabilidade.',
    'TEE Security': 'Seguranca TEE',
    'Your keys are managed in a Trusted Execution Environment. You authenticate; the enclave signs. No seed phrases to lose.':
      'Suas chaves sao gerenciadas em um Trusted Execution Environment. Voce autentica; o enclave assina.',
    'Gas Abstraction': 'Abstracao de gas',
    'Pay transaction fees in the same currency you send. No need to hold CELO just to pay for gas.':
      'Pague taxas na mesma moeda que envia. Nao precisa manter CELO apenas para gas.',
    'Ready to ditch the bank fees?': 'Pronto para largar as taxas bancarias?',
    'Join the thousands of users saving on every remittance with CeloFlow.':
      'Junte-se a milhares de usuarios economizando em cada remessa com CeloFlow.',
    'Enter your email': 'Digite seu email',
    'Get Early Access': 'Obter acesso antecipado',
    'Privacy Policy': 'Politica de privacidade',
    'Terms of Service': 'Termos de servico',
    Contact: 'Contato',
    '© 2024 CeloFlow. Built on Celo.': '© 2024 CeloFlow. Construido na Celo.',
    Connected: 'Conectado',
    Unknown: 'Desconhecido',
    Balance: 'Saldo',
    'Disconnect Wallet': 'Desconectar carteira',
    'Connect Wallet': 'Conectar carteira',
    'Connect a Wallet': 'Conectar carteira',
    'Copy address': 'Copiar endereco',
    'Smart Agent v2.1': 'Agente Inteligente v2.1',
    'AI that thinks like a': 'IA que pensa como um',
    'Market Maker.': 'market maker.',
    'CeloFlow scans decentralized exchanges (DEXs) and the Mento Protocol in real-time to find liquidity pools with the lowest slippage, ensuring your family gets the most out of every dollar sent.':
      'CeloFlow analisa DEX e o Protocolo Mento em tempo real para achar pools com menor slippage e maximizar cada dolar enviado.',
    Slippage: 'Slippage',
    'Route Time': 'Tempo de rota',
    'Avg. Savings': 'Economia media',
    'Route Optimization': 'Otimizacao de rota',
    Active: 'Ativo',
    Stablecoin: 'Stablecoin',
    Local: 'Local',
    'TEE Verification Complete': 'Verificacao TEE concluida',
    'Key management is handled inside a secure enclave. You never touch a private key.':
      'O gerenciamento de chaves ocorre em um enclave seguro. Voce nunca toca em uma chave privada.',
    All: 'Todos',
    Favorites: 'Favoritos',
    Blocked: 'Bloqueado',
    Sort: 'Ordenar',
    Name: 'Nome',
    Address: 'Endereco',
    Country: 'Pais',
    'Date Added': 'Data de cadastro',
    Export: 'Exportar',
    Import: 'Importar',
    Share: 'Compartilhar',
    'No matching contacts': 'Nenhum contato correspondente',
    'No contacts yet': 'Nenhum contato ainda',
    'Click + to add your first contact': 'Clique em + para adicionar seu primeiro contato',
    'Toggle favorite': 'Alternar favorito',
    'Toggle blocked': 'Alternar bloqueio',
    Edit: 'Editar',
    Delete: 'Excluir',
    'Delete Contact': 'Excluir contato',
    'This action cannot be undone.': 'Esta acao nao pode ser desfeita.',
    Cancel: 'Cancelar',
    'Edit Contact': 'Editar contato',
    'New Contact': 'Novo contato',
    'Name is required': 'Nome e obrigatorio',
    'Wallet Address': 'Endereco da carteira',
    'Address is required': 'Endereco e obrigatorio',
    Network: 'Rede',
    Phone: 'Telefone',
    Email: 'Email',
    'Invalid email format': 'Formato de email invalido',
    City: 'Cidade',
    'Avatar URL': 'URL do avatar',
    Group: 'Grupo',
    Notes: 'Notas',
    Favorite: 'Favorito',
    Update: 'Atualizar',
    Create: 'Criar',
    'John Doe': 'Joao Silva',
    '0x...': '0x...',
    '+1 234 567 8900': '+55 11 99999-9999',
    'john@example.com': 'joao@exemplo.com',
    Manila: 'Manila',
    Philippines: 'Filipinas',
    'https://...': 'https://...',
    'Family, Work, etc.': 'Familia, Trabalho, etc.',
    'Additional notes...': 'Notas adicionais...',
    'Contact updated': 'Contato atualizado',
    'Contact created': 'Contato criado',
    'Contact deleted': 'Contato removido',
    'Exported {{count}} contacts': '{{count}} contatos exportados',
    'Import failed': 'Falha na importacao',
    'Imported {{count}} contacts': '{{count}} contatos importados',
    ', {{count}} skipped': ', {{count}} ignorados',
    'No contacts to share': 'Nao ha contatos para compartilhar',
    'Contacts copied to clipboard': 'Contatos copiados para a area de transferencia',
    'Share failed': 'Falha ao compartilhar',
    'Address copied': 'Endereco copiado',
    '{{count}} contact': '{{count}} contato',
    '{{count}} contacts': '{{count}} contatos',
    'Add Contact': 'Adicionar contato',
    'Search contacts...': 'Buscar contatos...',
    'All Groups': 'Todos os grupos',
    'CeloFlow Contacts': 'Contatos CeloFlow',
    "Hi! I'm CeloFlow. I can help you send money globally using the Celo blockchain. Where would you like to send money today?":
      'Oi! Eu sou o CeloFlow. Posso ajudar voce a enviar dinheiro globalmente usando a blockchain Celo. Para onde voce quer enviar dinheiro hoje?',
    'Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.':
      'Entrada por voz nao e suportada neste navegador. Use Chrome, Edge ou Safari.',
    'Sorry, I encountered an error connecting to the server. Please try again.':
      'Desculpe, ocorreu um erro ao conectar ao servidor. Tente novamente.',
    'Are you sure you want to cancel this scheduled payment?':
      'Tem certeza que deseja cancelar este pagamento agendado?',
    'CeloFlow Transaction': 'Transacao CeloFlow',
    'I just sent {{amount}} {{currency}} to {{recipient}} via CeloFlow!':
      'Acabei de enviar {{amount}} {{currency}} para {{recipient}} via CeloFlow!',
    'Transaction details copied to clipboard!':
      'Detalhes da transacao copiados para a area de transferencia!',
    'Funds have successfully reached the recipient.':
      'Os fundos chegaram ao destinatario com sucesso.',
    'Transaction is currently being confirmed on the blockchain.':
      'A transacao esta sendo confirmada na blockchain.',
    'Payment is set to execute at a future date.':
      'O pagamento esta agendado para execucao futura.',
    'This transaction was cancelled by the user.':
      'Esta transacao foi cancelada pelo usuario.',
    'Transaction could not be completed. Please try again.':
      'A transacao nao pode ser concluida. Tente novamente.',
    Online: 'Online',
    'Transaction History': 'Historico de transacoes',
    'Recent Activity': 'Atividade recente',
    'Search recipient or currency...': 'Buscar destinatario ou moeda...',
    'No transactions yet.': 'Nenhuma transacao ainda.',
    'No matching transactions.': 'Nenhuma transacao correspondente.',
    'Cancel Scheduled Payment': 'Cancelar pagamento agendado',
    Sent: 'Enviado',
    Received: 'Recebido',
    '{{frequency}} starting {{startDate}}': '{{frequency}} a partir de {{startDate}}',
    'Best Quote Found': 'Melhor cotacao encontrada',
    'Saved ${{amount}}': 'Economizou ${{amount}}',
    'You Send': 'Voce envia',
    Receives: 'Recebe',
    'Live Real-time Rate': 'Cotacao em tempo real',
    'Estimated Fallback Rate': 'Cotacao estimada de backup',
    'Payment Schedule': 'Agendamento de pagamento',
    'One-time': 'Unico',
    Daily: 'Diario',
    Weekly: 'Semanal',
    Monthly: 'Mensal',
    'Mento Protocol Status': 'Status do Protocolo Mento',
    Optimal: 'Otimo',
    'Total Network Fees': 'Taxas totais de rede',
    'Mento Swap Fee': 'Taxa de swap Mento',
    'Celo Gas Fee': 'Taxa de gas Celo',
    'Secure Enclave (TEE)': 'Enclave seguro (TEE)',
    'Est. Arrival': 'Chegada estimada',
    '< 5 seconds': '< 5 segundos',
    Scheduled: 'Agendado',
    'Schedule Payment': 'Agendar pagamento',
    'Confirm Transfer': 'Confirmar transferencia',
    'Payment Scheduled!': 'Pagamento agendado!',
    'Transaction Sent!': 'Transacao enviada!',
    '{{amount}} {{currency}} will be sent to {{recipient}} {{frequency}} starting {{startDate}}.':
      '{{amount}} {{currency}} sera enviado para {{recipient}} {{frequency}} a partir de {{startDate}}.',
    '{{amount}} {{currency}} is on its way to {{recipient}}.':
      '{{amount}} {{currency}} esta a caminho de {{recipient}}.',
    'View on CeloScan': 'Ver no CeloScan',
    'Processing request...': 'Processando solicitacao...',
    'Speak to CeloFlow': 'Falar com CeloFlow',
    'Listening...': 'Ouvindo...',
    'Type a command...': 'Digite um comando...',
  },
  fr: {},
  de: {},
  it: {},
};

function isSupportedLanguage(value: string | null): value is SupportedLanguage {
  return LANGUAGE_OPTIONS.some((option) => option.code === value);
}

export function getStoredLanguage(): SupportedLanguage {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isSupportedLanguage(stored)) return stored;
  } catch {
    // Ignore storage read errors.
  }
  return 'en';
}

export function setStoredLanguage(language: SupportedLanguage): void {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Ignore storage write errors.
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent<SupportedLanguage>(LANGUAGE_EVENT, { detail: language }));
  }
}

export function useLanguage(): readonly [SupportedLanguage, (language: SupportedLanguage) => void] {
  const [language, setLanguage] = useState<SupportedLanguage>(getStoredLanguage);

  useEffect(() => {
    const handleLanguageChange = (event: Event) => {
      const customEvent = event as CustomEvent<SupportedLanguage>;
      if (customEvent.detail) {
        setLanguage(customEvent.detail);
        return;
      }
      setLanguage(getStoredLanguage());
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key === LANGUAGE_STORAGE_KEY && isSupportedLanguage(event.newValue)) {
        setLanguage(event.newValue);
      }
    };

    window.addEventListener(LANGUAGE_EVENT, handleLanguageChange as EventListener);
    window.addEventListener('storage', handleStorage);

    return () => {
      window.removeEventListener(LANGUAGE_EVENT, handleLanguageChange as EventListener);
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const updateLanguage = (nextLanguage: SupportedLanguage) => {
    setStoredLanguage(nextLanguage);
    setLanguage(nextLanguage);
  };

  return [language, updateLanguage] as const;
}

export function useI18n() {
  const [language, setLanguage] = useLanguage();

  const t = (text: string, params?: TranslationParams) => {
    return translate(language, text, params);
  };

  return {
    language,
    setLanguage,
    t,
  };
}
