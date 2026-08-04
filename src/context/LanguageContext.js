import React, { createContext, useContext, useState, useEffect } from 'react';

// Available languages
export const LANGUAGES = {
  en: { name: 'English', flag: '🇺🇸' },
  es: { name: 'Español', flag: '🇪🇸' },
  fr: { name: 'Français', flag: '🇫🇷' },
  de: { name: 'Deutsch', flag: '🇩🇪' },
  it: { name: 'Italiano', flag: '🇮🇹' },
  pt: { name: 'Português', flag: '🇧🇷' },
  zh: { name: '中文', flag: '🇨🇳' },
  ja: { name: '日本語', flag: '🇯🇵' },
  ko: { name: '한국어', flag: '🇰🇷' },
};

// Translations
const translations = {
  en: {
    // Common
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    edit: 'Edit',
    add: 'Add',
    search: 'Search',
    loading: 'Loading...',
    error: 'Error',
    success: 'Success',
    confirm: 'Confirm',
    back: 'Back',
    next: 'Next',
    done: 'Done',
    close: 'Close',
    
    // Navigation
    home: 'Home',
    recipes: 'Recipes',
    mealPlan: 'Meal Plan',
    shopping: 'Shopping',
    settings: 'Settings',
    admin: 'Admin',
    logout: 'Logout',
    
    // Auth
    signIn: 'Sign In',
    signUp: 'Sign Up',
    email: 'Email',
    password: 'Password',
    confirmPassword: 'Confirm Password',
    forgotPassword: 'Forgot Password?',
    resetPassword: 'Reset Password',
    
    // Recipes
    myRecipes: 'My Recipes',
    addRecipe: 'Add Recipe',
    importRecipe: 'Import Recipe',
    noRecipes: 'No recipes yet',
    ingredients: 'Ingredients',
    instructions: 'Instructions',
    servings: 'Servings',
    prepTime: 'Prep Time',
    cookTime: 'Cook Time',
    totalTime: 'Total Time',
    minutes: 'minutes',
    hours: 'hours',
    
    // Cook Mode
    startCooking: 'Start Cooking',
    step: 'Step',
    of: 'of',
    previous: 'Previous',
    askAI: 'Ask AI',
    aiAssistant: 'AI Assistant',
    typeQuestion: 'Type your question...',
    suggestedQuestions: 'Suggested questions',
    whatCanISubstitute: 'What can I substitute for {ingredient}?',
    howDoIKnowWhenDone: 'How do I know when it\'s done?',
    whatTemperature: 'What temperature should I use?',
    anyTips: 'Any tips for this step?',
    
    // Meal Planning
    weeklyPlan: 'Weekly Plan',
    breakfast: 'Breakfast',
    lunch: 'Lunch',
    dinner: 'Dinner',
    snacks: 'Snacks',
    addToMealPlan: 'Add to Meal Plan',
    generateMealPlan: 'Generate Meal Plan',
    
    // Shopping
    shoppingList: 'Shopping List',
    addItem: 'Add Item',
    clearCompleted: 'Clear Completed',
    
    // Settings
    language: 'Language',
    theme: 'Theme',
    lightMode: 'Light',
    darkMode: 'Dark',
    systemTheme: 'System',
    preferences: 'Preferences',
    security: 'Security',
    
    // Feedback
    wouldCookAgain: 'Would you cook this again?',
    yes: 'Yes!',
    no: 'No',
    maybe: 'Maybe',
    niceWork: 'Nice work, chef!',
  },
  
  es: {
    // Common
    save: 'Guardar',
    cancel: 'Cancelar',
    delete: 'Eliminar',
    edit: 'Editar',
    add: 'Añadir',
    search: 'Buscar',
    loading: 'Cargando...',
    error: 'Error',
    success: 'Éxito',
    confirm: 'Confirmar',
    back: 'Atrás',
    next: 'Siguiente',
    done: 'Hecho',
    close: 'Cerrar',
    
    // Navigation
    home: 'Inicio',
    recipes: 'Recetas',
    mealPlan: 'Plan de Comidas',
    shopping: 'Compras',
    settings: 'Ajustes',
    admin: 'Admin',
    logout: 'Cerrar Sesión',
    
    // Auth
    signIn: 'Iniciar Sesión',
    signUp: 'Registrarse',
    email: 'Correo',
    password: 'Contraseña',
    confirmPassword: 'Confirmar Contraseña',
    forgotPassword: '¿Olvidaste tu contraseña?',
    resetPassword: 'Restablecer Contraseña',
    
    // Recipes
    myRecipes: 'Mis Recetas',
    addRecipe: 'Añadir Receta',
    importRecipe: 'Importar Receta',
    noRecipes: 'No hay recetas',
    ingredients: 'Ingredientes',
    instructions: 'Instrucciones',
    servings: 'Porciones',
    prepTime: 'Tiempo de Prep.',
    cookTime: 'Tiempo de Cocción',
    totalTime: 'Tiempo Total',
    minutes: 'minutos',
    hours: 'horas',
    
    // Cook Mode
    startCooking: 'Empezar a Cocinar',
    step: 'Paso',
    of: 'de',
    previous: 'Anterior',
    askAI: 'Preguntar a IA',
    aiAssistant: 'Asistente IA',
    typeQuestion: 'Escribe tu pregunta...',
    suggestedQuestions: 'Preguntas sugeridas',
    whatCanISubstitute: '¿Qué puedo sustituir por {ingredient}?',
    howDoIKnowWhenDone: '¿Cómo sé cuándo está listo?',
    whatTemperature: '¿Qué temperatura debo usar?',
    anyTips: '¿Algún consejo para este paso?',
    
    // Meal Planning
    weeklyPlan: 'Plan Semanal',
    breakfast: 'Desayuno',
    lunch: 'Almuerzo',
    dinner: 'Cena',
    snacks: 'Snacks',
    addToMealPlan: 'Añadir al Plan',
    generateMealPlan: 'Generar Plan',
    
    // Shopping
    shoppingList: 'Lista de Compras',
    addItem: 'Añadir Artículo',
    clearCompleted: 'Borrar Completados',
    
    // Settings
    language: 'Idioma',
    theme: 'Tema',
    lightMode: 'Claro',
    darkMode: 'Oscuro',
    systemTheme: 'Sistema',
    preferences: 'Preferencias',
    security: 'Seguridad',
    
    // Feedback
    wouldCookAgain: '¿Lo cocinarías de nuevo?',
    yes: '¡Sí!',
    no: 'No',
    maybe: 'Tal vez',
    niceWork: '¡Buen trabajo, chef!',
  },
  
  fr: {
    // Common
    save: 'Enregistrer',
    cancel: 'Annuler',
    delete: 'Supprimer',
    edit: 'Modifier',
    add: 'Ajouter',
    search: 'Rechercher',
    loading: 'Chargement...',
    error: 'Erreur',
    success: 'Succès',
    confirm: 'Confirmer',
    back: 'Retour',
    next: 'Suivant',
    done: 'Terminé',
    close: 'Fermer',
    
    // Navigation
    home: 'Accueil',
    recipes: 'Recettes',
    mealPlan: 'Plan Repas',
    shopping: 'Courses',
    settings: 'Paramètres',
    admin: 'Admin',
    logout: 'Déconnexion',
    
    // Auth
    signIn: 'Se Connecter',
    signUp: "S'inscrire",
    email: 'Email',
    password: 'Mot de passe',
    confirmPassword: 'Confirmer le mot de passe',
    forgotPassword: 'Mot de passe oublié?',
    resetPassword: 'Réinitialiser',
    
    // Recipes
    myRecipes: 'Mes Recettes',
    addRecipe: 'Ajouter Recette',
    importRecipe: 'Importer Recette',
    noRecipes: 'Pas de recettes',
    ingredients: 'Ingrédients',
    instructions: 'Instructions',
    servings: 'Portions',
    prepTime: 'Temps de Prép.',
    cookTime: 'Temps de Cuisson',
    totalTime: 'Temps Total',
    minutes: 'minutes',
    hours: 'heures',
    
    // Cook Mode
    startCooking: 'Commencer à Cuisiner',
    step: 'Étape',
    of: 'sur',
    previous: 'Précédent',
    askAI: 'Demander à l\'IA',
    aiAssistant: 'Assistant IA',
    typeQuestion: 'Tapez votre question...',
    suggestedQuestions: 'Questions suggérées',
    whatCanISubstitute: 'Par quoi remplacer {ingredient}?',
    howDoIKnowWhenDone: 'Comment savoir si c\'est prêt?',
    whatTemperature: 'Quelle température utiliser?',
    anyTips: 'Des conseils pour cette étape?',
    
    // Meal Planning
    weeklyPlan: 'Plan Hebdomadaire',
    breakfast: 'Petit-déjeuner',
    lunch: 'Déjeuner',
    dinner: 'Dîner',
    snacks: 'Encas',
    addToMealPlan: 'Ajouter au Plan',
    generateMealPlan: 'Générer un Plan',
    
    // Shopping
    shoppingList: 'Liste de Courses',
    addItem: 'Ajouter Article',
    clearCompleted: 'Effacer Terminés',
    
    // Settings
    language: 'Langue',
    theme: 'Thème',
    lightMode: 'Clair',
    darkMode: 'Sombre',
    systemTheme: 'Système',
    preferences: 'Préférences',
    security: 'Sécurité',
    
    // Feedback
    wouldCookAgain: 'Le recuisineriez-vous?',
    yes: 'Oui!',
    no: 'Non',
    maybe: 'Peut-être',
    niceWork: 'Bien joué, chef!',
  },
  
  de: {
    save: 'Speichern',
    cancel: 'Abbrechen',
    delete: 'Löschen',
    edit: 'Bearbeiten',
    add: 'Hinzufügen',
    search: 'Suchen',
    loading: 'Laden...',
    home: 'Startseite',
    recipes: 'Rezepte',
    mealPlan: 'Essensplan',
    shopping: 'Einkaufen',
    settings: 'Einstellungen',
    signIn: 'Anmelden',
    signUp: 'Registrieren',
    ingredients: 'Zutaten',
    instructions: 'Anleitung',
    servings: 'Portionen',
    startCooking: 'Kochen starten',
    askAI: 'KI fragen',
    aiAssistant: 'KI-Assistent',
    language: 'Sprache',
    niceWork: 'Gut gemacht, Koch!',
  },
  
  it: {
    save: 'Salva',
    cancel: 'Annulla',
    delete: 'Elimina',
    edit: 'Modifica',
    add: 'Aggiungi',
    search: 'Cerca',
    loading: 'Caricamento...',
    home: 'Home',
    recipes: 'Ricette',
    mealPlan: 'Piano Pasti',
    shopping: 'Spesa',
    settings: 'Impostazioni',
    signIn: 'Accedi',
    signUp: 'Registrati',
    ingredients: 'Ingredienti',
    instructions: 'Istruzioni',
    servings: 'Porzioni',
    startCooking: 'Inizia a Cucinare',
    askAI: 'Chiedi all\'IA',
    aiAssistant: 'Assistente IA',
    language: 'Lingua',
    niceWork: 'Ottimo lavoro, chef!',
  },
  
  pt: {
    save: 'Salvar',
    cancel: 'Cancelar',
    delete: 'Excluir',
    edit: 'Editar',
    add: 'Adicionar',
    search: 'Buscar',
    loading: 'Carregando...',
    home: 'Início',
    recipes: 'Receitas',
    mealPlan: 'Plano de Refeições',
    shopping: 'Compras',
    settings: 'Configurações',
    signIn: 'Entrar',
    signUp: 'Cadastrar',
    ingredients: 'Ingredientes',
    instructions: 'Instruções',
    servings: 'Porções',
    startCooking: 'Começar a Cozinhar',
    askAI: 'Perguntar à IA',
    aiAssistant: 'Assistente IA',
    language: 'Idioma',
    niceWork: 'Bom trabalho, chef!',
  },
  
  zh: {
    save: '保存',
    cancel: '取消',
    delete: '删除',
    edit: '编辑',
    add: '添加',
    search: '搜索',
    loading: '加载中...',
    home: '首页',
    recipes: '食谱',
    mealPlan: '餐计划',
    shopping: '购物',
    settings: '设置',
    signIn: '登录',
    signUp: '注册',
    ingredients: '食材',
    instructions: '步骤',
    servings: '份量',
    startCooking: '开始烹饪',
    askAI: '问AI',
    aiAssistant: 'AI助手',
    language: '语言',
    niceWork: '干得好，大厨!',
  },
  
  ja: {
    save: '保存',
    cancel: 'キャンセル',
    delete: '削除',
    edit: '編集',
    add: '追加',
    search: '検索',
    loading: '読み込み中...',
    home: 'ホーム',
    recipes: 'レシピ',
    mealPlan: '献立',
    shopping: '買い物',
    settings: '設定',
    signIn: 'ログイン',
    signUp: '登録',
    ingredients: '材料',
    instructions: '手順',
    servings: '人分',
    startCooking: '調理を開始',
    askAI: 'AIに質問',
    aiAssistant: 'AIアシスタント',
    language: '言語',
    niceWork: 'よくできました、シェフ!',
  },
  
  ko: {
    save: '저장',
    cancel: '취소',
    delete: '삭제',
    edit: '수정',
    add: '추가',
    search: '검색',
    loading: '로딩 중...',
    home: '홈',
    recipes: '레시피',
    mealPlan: '식단',
    shopping: '장보기',
    settings: '설정',
    signIn: '로그인',
    signUp: '회원가입',
    ingredients: '재료',
    instructions: '조리법',
    servings: '인분',
    startCooking: '요리 시작',
    askAI: 'AI에게 물어보기',
    aiAssistant: 'AI 어시스턴트',
    language: '언어',
    niceWork: '잘했어요, 셰프!',
  },
};

const LanguageContext = createContext();

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider');
  }
  return context;
};

export const LanguageProvider = ({ children }) => {
  const [language, setLanguage] = useState(() => {
    const saved = localStorage.getItem('laro_language');
    if (saved && translations[saved]) return saved;
    
    // Detect browser language
    const browserLang = navigator.language.split('-')[0];
    if (translations[browserLang]) return browserLang;
    
    return 'en';
  });

  useEffect(() => {
    localStorage.setItem('laro_language', language);
    document.documentElement.lang = language;
  }, [language]);

  // Translation function
  const t = (key, params = {}) => {
    let text = translations[language]?.[key] || translations.en[key] || key;
    
    // Replace parameters like {ingredient}
    Object.entries(params).forEach(([param, value]) => {
      text = text.replace(`{${param}}`, value);
    });
    
    return text;
  };

  const value = {
    language,
    setLanguage,
    t,
    languages: LANGUAGES,
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};
