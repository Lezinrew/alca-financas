# 🔥 PROMPT: Migração Completa do Alca Finanças para Firebase Google

## 📋 Objetivo
Migrar completamente o projeto **Alca Finanças** do stack atual (MongoDB/Supabase + Flask + JWT) para Firebase Google, utilizando Firestore, Firebase Authentication, Cloud Functions e Firebase Storage, mantendo todas as funcionalidades existentes e otimizando a arquitetura para o ecossistema Google.

---

## 🏗️ Arquitetura Atual vs Firebase

### Stack Atual
- **Backend**: Flask (Python) com API REST
- **Banco de Dados**: MongoDB (principal) ou Supabase/PostgreSQL
- **Autenticação**: JWT customizado + OAuth (Authlib) + bcrypt
- **Armazenamento**: Sistema de arquivos local (profile_picture)
- **Deploy**: Docker + servidor tradicional
- **API**: Axios com interceptors e Authorization Bearer token

### Stack Alvo (Firebase)
- **Backend**: Firebase Cloud Functions (Python ou Node.js)
- **Banco de Dados**: Cloud Firestore (NoSQL)
- **Autenticação**: Firebase Authentication (Email/Password + OAuth providers)
- **Armazenamento**: Firebase Storage (profile pictures, CSV imports)
- **Deploy**: Firebase Hosting + Cloud Functions
- **API**: Firebase SDK (cliente) com Auth state management
- **Regras de Segurança**: Firestore Security Rules + Storage Rules

---

## 📊 Mapeamento de Dados: MongoDB/PostgreSQL → Firestore

### 1. Estrutura de Collections

#### **Collection: `users`**
```javascript
users/{userId}
{
  email: string,
  name: string,
  // password NÃO é armazenado (Firebase Auth gerencia)
  settings: {
    theme: string,
    language: string,
    currency: string,
    notifications: boolean
  },
  authProviders: {
    google: boolean,
    microsoft: boolean,
    apple: boolean
  },
  isAdmin: boolean,
  profilePicture: string, // URL do Firebase Storage
  createdAt: timestamp,
  updatedAt: timestamp
}
```

**Índices Firestore:**
- `email` (ASC)
- `createdAt` (DESC)

#### **Collection: `categories`**
```javascript
categories/{categoryId}
{
  userId: string, // Referência ao user
  name: string,
  type: string, // 'income' | 'expense'
  color: string,
  icon: string,
  description: string,
  active: boolean,
  essential: boolean,
  createdAt: timestamp,
  updatedAt: timestamp
}
```

**Índices Compostos:**
- `userId` (ASC) + `type` (ASC)
- `userId` (ASC) + `active` (ASC)
- `userId` (ASC) + `createdAt` (DESC)

#### **Collection: `accounts`**
```javascript
accounts/{accountId}
{
  userId: string,
  name: string,
  type: string, // 'bank' | 'credit_card' | 'savings' | 'wallet' | 'investment'
  color: string,
  icon: string,
  balance: number,
  currency: string,
  active: boolean,
  createdAt: timestamp,
  updatedAt: timestamp
}
```

**Índices Compostos:**
- `userId` (ASC) + `type` (ASC)
- `userId` (ASC) + `active` (ASC)

#### **Collection: `transactions`**
```javascript
transactions/{transactionId}
{
  userId: string,
  categoryId: string, // Referência
  accountId: string, // Referência
  description: string,
  amount: number,
  type: string, // 'income' | 'expense'
  date: timestamp,
  status: string, // 'paid' | 'pending' | 'overdue' | 'cancelled'
  responsiblePerson: string,
  isRecurring: boolean,
  installmentInfo: {
    currentInstallment: number,
    totalInstallments: number,
    originalTransactionId: string
  },
  tags: [string],
  notes: string,
  createdAt: timestamp,
  updatedAt: timestamp
}
```

**Índices Compostos (CRÍTICOS para performance):**
- `userId` (ASC) + `date` (DESC)
- `userId` (ASC) + `type` (ASC) + `date` (DESC)
- `userId` (ASC) + `status` (ASC)
- `userId` (ASC) + `categoryId` (ASC)
- `userId` (ASC) + `accountId` (ASC)
- `userId` (ASC) + `isRecurring` (ASC)

#### **Collection: `oauthStates` (temporária)**
```javascript
oauthStates/{stateId}
{
  state: string,
  provider: string, // 'google' | 'microsoft' | 'apple'
  createdAt: timestamp,
  expiresAt: timestamp
}
```

**TTL (Time To Live):** Configurar exclusão automática após `expiresAt` usando Cloud Functions

---

## 🔐 Firestore Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Helper functions
    function isSignedIn() {
      return request.auth != null;
    }

    function isOwner(userId) {
      return isSignedIn() && request.auth.uid == userId;
    }

    function isAdmin() {
      return isSignedIn() &&
             get(/databases/$(database)/documents/users/$(request.auth.uid)).data.isAdmin == true;
    }

    // Users collection
    match /users/{userId} {
      // Qualquer usuário autenticado pode ler seu próprio documento
      allow read: if isOwner(userId);

      // Usuário pode atualizar apenas seu próprio documento
      allow update: if isOwner(userId) &&
                      // Não pode alterar isAdmin ou email
                      !request.resource.data.diff(resource.data).affectedKeys().hasAny(['isAdmin', 'email']);

      // Admin pode ler todos os usuários
      allow read: if isAdmin();

      // Criação de usuário é gerenciada via Cloud Functions (não via cliente)
      allow create: if false;
      allow delete: if false;
    }

    // Categories collection
    match /categories/{categoryId} {
      allow read: if isOwner(resource.data.userId);
      allow create: if isSignedIn() && request.resource.data.userId == request.auth.uid;
      allow update, delete: if isOwner(resource.data.userId);
    }

    // Accounts collection
    match /accounts/{accountId} {
      allow read: if isOwner(resource.data.userId);
      allow create: if isSignedIn() && request.resource.data.userId == request.auth.uid;
      allow update, delete: if isOwner(resource.data.userId);
    }

    // Transactions collection
    match /transactions/{transactionId} {
      allow read: if isOwner(resource.data.userId);
      allow create: if isSignedIn() &&
                      request.resource.data.userId == request.auth.uid &&
                      // Valida que category e account pertencem ao usuário
                      exists(/databases/$(database)/documents/categories/$(request.resource.data.categoryId)) &&
                      exists(/databases/$(database)/documents/accounts/$(request.resource.data.accountId));
      allow update, delete: if isOwner(resource.data.userId);
    }

    // OAuth States (temporário, usado no fluxo OAuth)
    match /oauthStates/{stateId} {
      allow read, create: if isSignedIn();
      allow delete: if isSignedIn(); // Cloud Function também pode deletar
    }
  }
}
```

---

## 🔒 Firebase Storage Rules

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {

    // Profile pictures
    match /profile_pictures/{userId}/{fileName} {
      // Apenas o usuário pode ler/escrever sua própria foto
      allow read: if request.auth != null && request.auth.uid == userId;
      allow write: if request.auth != null &&
                     request.auth.uid == userId &&
                     request.resource.size < 5 * 1024 * 1024 && // Máximo 5MB
                     request.resource.contentType.matches('image/.*');
    }

    // CSV import files (temporário)
    match /csv_imports/{userId}/{fileName} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
      // Cloud Function fará limpeza automática após processamento
    }
  }
}
```

---

## 🔧 Migração do Backend

### 1. Substituir Flask por Cloud Functions

#### **Estrutura de Diretórios (Cloud Functions - Python)**
```
functions/
├── main.py                    # Funções HTTP e triggers
├── requirements.txt
├── services/
│   ├── user_service.py
│   ├── transaction_service.py
│   ├── category_service.py
│   ├── account_service.py
│   ├── report_service.py
│   ├── import_service.py
│   └── category_detector.py
├── utils/
│   ├── firestore_helpers.py
│   ├── auth_decorators.py
│   └── exceptions.py
└── schemas/
    └── validation.py
```

#### **requirements.txt (Firebase)**
```txt
firebase-admin==6.4.0
firebase-functions==0.4.0
google-cloud-firestore==2.14.0
google-cloud-storage==2.14.0
pandas==2.2.0
python-dateutil==2.8.2
```

#### **Exemplo: main.py (Cloud Functions HTTP)**
```python
import firebase_admin
from firebase_admin import auth, firestore, storage
from firebase_functions import https_fn, options
from services import transaction_service, category_service, account_service

# Inicializa Firebase Admin SDK
firebase_admin.initialize_app()

# Obter instâncias
db = firestore.client()
bucket = storage.bucket()

# CORS configurado globalmente
cors_options = options.CorsOptions(
    cors_origins=["https://seu-dominio.web.app", "http://localhost:5173"],
    cors_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# ==================== TRANSACTIONS ====================

@https_fn.on_request(cors=cors_options)
def get_transactions(req: https_fn.Request) -> https_fn.Response:
    """GET /api/transactions - Lista transações do usuário autenticado"""
    try:
        # Validar token Firebase
        token = req.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return https_fn.Response({"error": "Unauthorized"}, status=401)

        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']

        # Parâmetros de filtro
        start_date = req.args.get('start_date')
        end_date = req.args.get('end_date')
        category_id = req.args.get('category_id')

        # Buscar transações (delegado ao service)
        transactions = transaction_service.get_user_transactions(
            db, user_id, start_date, end_date, category_id
        )

        return https_fn.Response({"transactions": transactions}, status=200)

    except auth.InvalidIdTokenError:
        return https_fn.Response({"error": "Invalid token"}, status=401)
    except Exception as e:
        return https_fn.Response({"error": str(e)}, status=500)


@https_fn.on_request(cors=cors_options)
def create_transaction(req: https_fn.Request) -> https_fn.Response:
    """POST /api/transactions - Cria nova transação"""
    try:
        token = req.headers.get('Authorization', '').replace('Bearer ', '')
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']

        data = req.get_json()

        # Validação (usando Pydantic ou similar)
        # ...

        # Criar transação
        transaction_id = transaction_service.create_transaction(db, user_id, data)

        return https_fn.Response({"id": transaction_id, "message": "Created"}, status=201)

    except Exception as e:
        return https_fn.Response({"error": str(e)}, status=500)


# ==================== CATEGORIES ====================

@https_fn.on_request(cors=cors_options)
def get_categories(req: https_fn.Request) -> https_fn.Response:
    """GET /api/categories"""
    try:
        token = req.headers.get('Authorization', '').replace('Bearer ', '')
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']

        categories = category_service.get_user_categories(db, user_id)

        return https_fn.Response({"categories": categories}, status=200)
    except Exception as e:
        return https_fn.Response({"error": str(e)}, status=500)


# ==================== AUTH TRIGGERS ====================

@https_fn.on_call()
def on_user_create(event):
    """Trigger: Cria documento no Firestore quando usuário é criado no Firebase Auth"""
    user = event.data
    user_id = user.uid

    # Criar documento inicial do usuário
    db.collection('users').document(user_id).set({
        'email': user.email,
        'name': user.display_name or '',
        'settings': {
            'theme': 'light',
            'language': 'pt-BR',
            'currency': 'BRL',
            'notifications': True
        },
        'authProviders': {
            'google': False,
            'microsoft': False,
            'apple': False
        },
        'isAdmin': False,
        'profilePicture': '',
        'createdAt': firestore.SERVER_TIMESTAMP,
        'updatedAt': firestore.SERVER_TIMESTAMP
    })

    # Criar categorias padrão
    category_service.create_default_categories(db, user_id)

    return {"success": True}


# ==================== CSV IMPORT ====================

@https_fn.on_request(cors=cors_options)
def import_csv(req: https_fn.Request) -> https_fn.Response:
    """POST /api/import/csv - Upload e processamento de CSV"""
    try:
        token = req.headers.get('Authorization', '').replace('Bearer ', '')
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']

        # Upload para Storage
        file = req.files['file']
        blob = bucket.blob(f'csv_imports/{user_id}/{file.filename}')
        blob.upload_from_file(file)

        # Processar CSV (pandas)
        from services.import_service import process_csv_import
        result = process_csv_import(db, user_id, blob)

        # Deletar arquivo após processamento
        blob.delete()

        return https_fn.Response(result, status=200)

    except Exception as e:
        return https_fn.Response({"error": str(e)}, status=500)


# ==================== CLEANUP TRIGGERS ====================

@https_fn.on_schedule(schedule="every 24 hours")
def cleanup_expired_oauth_states(event):
    """Limpa estados OAuth expirados"""
    now = firestore.SERVER_TIMESTAMP

    expired_states = db.collection('oauthStates').where('expiresAt', '<', now).stream()

    for state in expired_states:
        state.reference.delete()

    return {"cleaned": True}
```

### 2. Services Layer (Exemplo: transaction_service.py)

```python
from google.cloud import firestore
from datetime import datetime
from typing import List, Dict, Optional

def get_user_transactions(
    db: firestore.Client,
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_id: Optional[str] = None
) -> List[Dict]:
    """Busca transações do usuário com filtros"""

    # Query base
    query = db.collection('transactions').where('userId', '==', user_id)

    # Filtros opcionais
    if start_date:
        query = query.where('date', '>=', datetime.fromisoformat(start_date))
    if end_date:
        query = query.where('date', '<=', datetime.fromisoformat(end_date))
    if category_id:
        query = query.where('categoryId', '==', category_id)

    # Ordenação
    query = query.order_by('date', direction=firestore.Query.DESCENDING)

    # Executar
    docs = query.stream()

    transactions = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        transactions.append(data)

    return transactions


def create_transaction(
    db: firestore.Client,
    user_id: str,
    data: Dict
) -> str:
    """Cria nova transação"""

    # Adicionar campos de controle
    data['userId'] = user_id
    data['createdAt'] = firestore.SERVER_TIMESTAMP
    data['updatedAt'] = firestore.SERVER_TIMESTAMP

    # Converter date para timestamp se necessário
    if isinstance(data.get('date'), str):
        data['date'] = datetime.fromisoformat(data['date'])

    # Criar documento
    doc_ref = db.collection('transactions').add(data)

    # Atualizar saldo da conta (se necessário)
    update_account_balance(db, data['accountId'], data['amount'], data['type'])

    return doc_ref[1].id


def update_account_balance(
    db: firestore.Client,
    account_id: str,
    amount: float,
    transaction_type: str
):
    """Atualiza saldo da conta atomicamente"""

    account_ref = db.collection('accounts').document(account_id)

    @firestore.transactional
    def update_in_transaction(transaction, account_ref, amount, tx_type):
        account = transaction.get(account_ref)
        current_balance = account.to_dict()['balance']

        if tx_type == 'income':
            new_balance = current_balance + amount
        else:  # expense
            new_balance = current_balance - amount

        transaction.update(account_ref, {
            'balance': new_balance,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })

    transaction = db.transaction()
    update_in_transaction(transaction, account_ref, amount, transaction_type)
```

---

## 💻 Migração do Frontend

### 1. Instalar Firebase SDK

```bash
cd frontend
npm install firebase
```

### 2. Configurar Firebase (firebase-config.ts)

```typescript
// src/firebase-config.ts
import { initializeApp } from 'firebase/app';
import { getAuth, connectAuthEmulator } from 'firebase/auth';
import { getFirestore, connectFirestoreEmulator } from 'firebase/firestore';
import { getStorage, connectStorageEmulator } from 'firebase/storage';
import { getFunctions, connectFunctionsEmulator } from 'firebase/functions';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

// Inicializar Firebase
const app = initializeApp(firebaseConfig);

// Serviços
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);
export const functions = getFunctions(app);

// Emulators (desenvolvimento local)
if (import.meta.env.DEV) {
  connectAuthEmulator(auth, 'http://localhost:9099');
  connectFirestoreEmulator(db, 'localhost', 8080);
  connectStorageEmulator(storage, 'localhost', 9199);
  connectFunctionsEmulator(functions, 'localhost', 5001);
}
```

### 3. Atualizar AuthContext

```typescript
// src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  User,
  GoogleAuthProvider,
  signInWithPopup
} from 'firebase/auth';
import { doc, getDoc, setDoc } from 'firebase/firestore';
import { auth, db } from '../firebase-config';

interface UserData {
  id: string;
  email: string;
  name: string;
  isAdmin: boolean;
  settings: any;
}

interface AuthContextType {
  user: UserData | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  loginWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  // Escutar mudanças de autenticação
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        // Buscar dados do usuário no Firestore
        const userDoc = await getDoc(doc(db, 'users', firebaseUser.uid));
        if (userDoc.exists()) {
          setUser({
            id: firebaseUser.uid,
            email: firebaseUser.email!,
            ...userDoc.data()
          } as UserData);
        }
      } else {
        setUser(null);
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const login = async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password);
  };

  const register = async (email: string, password: string, name: string) => {
    const credential = await createUserWithEmailAndPassword(auth, email, password);

    // Criar documento do usuário no Firestore
    await setDoc(doc(db, 'users', credential.user.uid), {
      email: credential.user.email,
      name,
      settings: {
        theme: 'light',
        language: 'pt-BR',
        currency: 'BRL',
        notifications: true
      },
      authProviders: {
        google: false
      },
      isAdmin: false,
      profilePicture: '',
      createdAt: new Date(),
      updatedAt: new Date()
    });
  };

  const loginWithGoogle = async () => {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
  };

  const logout = async () => {
    await firebaseSignOut(auth);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        register,
        loginWithGoogle,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

### 4. Substituir API calls por Firestore SDK

**ANTES (Axios):**
```typescript
// src/utils/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;

// Uso
const response = await api.get('/transactions');
```

**DEPOIS (Firebase SDK):**
```typescript
// src/services/transactionService.ts
import {
  collection,
  query,
  where,
  getDocs,
  addDoc,
  updateDoc,
  deleteDoc,
  doc,
  orderBy,
  Timestamp
} from 'firebase/firestore';
import { db } from '../firebase-config';
import { auth } from '../firebase-config';

export const getTransactions = async (startDate?: Date, endDate?: Date, categoryId?: string) => {
  const userId = auth.currentUser?.uid;
  if (!userId) throw new Error('User not authenticated');

  let q = query(
    collection(db, 'transactions'),
    where('userId', '==', userId),
    orderBy('date', 'desc')
  );

  if (startDate) {
    q = query(q, where('date', '>=', Timestamp.fromDate(startDate)));
  }

  if (endDate) {
    q = query(q, where('date', '<=', Timestamp.fromDate(endDate)));
  }

  if (categoryId) {
    q = query(q, where('categoryId', '==', categoryId));
  }

  const snapshot = await getDocs(q);
  return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
};

export const createTransaction = async (data: any) => {
  const userId = auth.currentUser?.uid;
  if (!userId) throw new Error('User not authenticated');

  const docRef = await addDoc(collection(db, 'transactions'), {
    ...data,
    userId,
    date: Timestamp.fromDate(new Date(data.date)),
    createdAt: Timestamp.now(),
    updatedAt: Timestamp.now()
  });

  return docRef.id;
};

export const updateTransaction = async (id: string, data: any) => {
  const docRef = doc(db, 'transactions', id);
  await updateDoc(docRef, {
    ...data,
    updatedAt: Timestamp.now()
  });
};

export const deleteTransaction = async (id: string) => {
  await deleteDoc(doc(db, 'transactions', id));
};
```

### 5. Real-time Listeners (Bonus)

```typescript
// src/hooks/useTransactions.ts
import { useEffect, useState } from 'react';
import { collection, query, where, onSnapshot, orderBy } from 'firebase/firestore';
import { db, auth } from '../firebase-config';

export const useTransactions = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userId = auth.currentUser?.uid;
    if (!userId) return;

    const q = query(
      collection(db, 'transactions'),
      where('userId', '==', userId),
      orderBy('date', 'desc')
    );

    // Listener em tempo real
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setTransactions(data);
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  return { transactions, loading };
};
```

---

## 📦 Script de Migração de Dados

```python
# migrate_to_firebase.py
import firebase_admin
from firebase_admin import credentials, firestore
from pymongo import MongoClient
from datetime import datetime
import os

# Inicializar Firebase Admin
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Conectar MongoDB
mongo_client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
mongo_db = mongo_client['alca_financas']

def migrate_users():
    """Migra usuários do MongoDB para Firestore"""
    print("Migrando usuários...")

    users_collection = mongo_db['users']
    users = users_collection.find()

    batch = db.batch()
    count = 0

    for user in users:
        user_id = str(user['_id'])

        # Criar usuário no Firebase Auth primeiro
        from firebase_admin import auth
        try:
            firebase_user = auth.create_user(
                uid=user_id,
                email=user['email'],
                display_name=user.get('name', ''),
                password=user.get('password', '')  # Se disponível
            )
        except Exception as e:
            print(f"Erro ao criar usuário {user['email']}: {e}")
            continue

        # Criar documento no Firestore
        user_ref = db.collection('users').document(user_id)
        batch.set(user_ref, {
            'email': user['email'],
            'name': user.get('name', ''),
            'settings': user.get('settings', {}),
            'authProviders': user.get('auth_providers', {}),
            'isAdmin': user.get('is_admin', False),
            'profilePicture': user.get('profile_picture', ''),
            'createdAt': user.get('created_at', datetime.now()),
            'updatedAt': user.get('updated_at', datetime.now())
        })

        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  {count} usuários migrados...")

    batch.commit()
    print(f"✓ {count} usuários migrados com sucesso")


def migrate_categories():
    """Migra categorias"""
    print("Migrando categorias...")

    categories_collection = mongo_db['categories']
    categories = categories_collection.find()

    batch = db.batch()
    count = 0

    for category in categories:
        category_id = str(category['_id'])
        category_ref = db.collection('categories').document(category_id)

        batch.set(category_ref, {
            'userId': str(category['user_id']),
            'name': category['name'],
            'type': category['type'],
            'color': category.get('color', ''),
            'icon': category.get('icon', ''),
            'description': category.get('description', ''),
            'active': category.get('active', True),
            'essential': category.get('essential', False),
            'createdAt': category.get('created_at', datetime.now()),
            'updatedAt': category.get('updated_at', datetime.now())
        })

        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  {count} categorias migradas...")

    batch.commit()
    print(f"✓ {count} categorias migradas com sucesso")


def migrate_accounts():
    """Migra contas"""
    print("Migrando contas...")

    accounts_collection = mongo_db['accounts']
    accounts = accounts_collection.find()

    batch = db.batch()
    count = 0

    for account in accounts:
        account_id = str(account['_id'])
        account_ref = db.collection('accounts').document(account_id)

        batch.set(account_ref, {
            'userId': str(account['user_id']),
            'name': account['name'],
            'type': account['type'],
            'color': account.get('color', ''),
            'icon': account.get('icon', ''),
            'balance': account.get('balance', 0),
            'currency': account.get('currency', 'BRL'),
            'active': account.get('active', True),
            'createdAt': account.get('created_at', datetime.now()),
            'updatedAt': account.get('updated_at', datetime.now())
        })

        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  {count} contas migradas...")

    batch.commit()
    print(f"✓ {count} contas migradas com sucesso")


def migrate_transactions():
    """Migra transações"""
    print("Migrando transações...")

    transactions_collection = mongo_db['transactions']
    transactions = transactions_collection.find()

    batch = db.batch()
    count = 0

    for transaction in transactions:
        transaction_id = str(transaction['_id'])
        transaction_ref = db.collection('transactions').document(transaction_id)

        batch.set(transaction_ref, {
            'userId': str(transaction['user_id']),
            'categoryId': str(transaction.get('category_id', '')),
            'accountId': str(transaction.get('account_id', '')),
            'description': transaction['description'],
            'amount': transaction['amount'],
            'type': transaction['type'],
            'date': transaction['date'],
            'status': transaction.get('status', 'paid'),
            'responsiblePerson': transaction.get('responsible_person', ''),
            'isRecurring': transaction.get('is_recurring', False),
            'installmentInfo': transaction.get('installment_info', {}),
            'tags': transaction.get('tags', []),
            'notes': transaction.get('notes', ''),
            'createdAt': transaction.get('created_at', datetime.now()),
            'updatedAt': transaction.get('updated_at', datetime.now())
        })

        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  {count} transações migradas...")

    batch.commit()
    print(f"✓ {count} transações migradas com sucesso")


if __name__ == '__main__':
    print("=== INICIANDO MIGRAÇÃO PARA FIREBASE ===\n")

    migrate_users()
    migrate_categories()
    migrate_accounts()
    migrate_transactions()

    print("\n=== MIGRAÇÃO CONCLUÍDA ===")
```

---

## 🚀 Passos de Implementação

### Fase 1: Setup Firebase (1-2 dias)
1. Criar projeto no Firebase Console
2. Habilitar Authentication (Email/Password, Google, Microsoft)
3. Criar database Firestore
4. Configurar Storage
5. Instalar Firebase CLI: `npm install -g firebase-tools`
6. Login: `firebase login`
7. Inicializar projeto: `firebase init`

### Fase 2: Migração de Dados (2-3 dias)
1. Exportar dados do MongoDB/Supabase
2. Ajustar script de migração
3. Executar migração em ambiente de teste
4. Validar integridade dos dados
5. Criar índices compostos no Firestore

### Fase 3: Backend - Cloud Functions (5-7 dias)
1. Criar estrutura de functions/
2. Implementar autenticação com Firebase Admin SDK
3. Converter endpoints Flask para Cloud Functions HTTP
4. Migrar services layer
5. Implementar triggers (onCreate, onSchedule)
6. Testar localmente com emulators
7. Deploy para Firebase

### Fase 4: Frontend - SDK Firebase (4-6 dias)
1. Instalar Firebase SDK
2. Configurar firebase-config.ts
3. Atualizar AuthContext para Firebase Auth
4. Substituir Axios por Firestore SDK
5. Implementar real-time listeners (opcional)
6. Atualizar componentes (Login, Register, Dashboard, etc.)
7. Testar com emulators
8. Deploy para Firebase Hosting

### Fase 5: Security Rules (2-3 dias)
1. Implementar Firestore Security Rules
2. Implementar Storage Rules
3. Testar com diferentes usuários
4. Validar permissões admin

### Fase 6: Testes e Otimização (3-5 dias)
1. Testes de integração E2E (Playwright)
2. Testes de performance
3. Otimizar queries e índices
4. Configurar monitoring (Firebase Analytics)
5. Configurar alertas de erro (Firebase Crashlytics)

### Fase 7: Deploy e Migração Final (2-3 dias)
1. Backup completo do banco atual
2. Migração de dados de produção
3. Deploy de production
4. Monitoramento intensivo
5. Rollback plan preparado

---

## 📝 Checklist de Migração

### Preparação
- [ ] Criar projeto Firebase
- [ ] Configurar Authentication providers
- [ ] Criar database Firestore
- [ ] Habilitar Storage
- [ ] Instalar Firebase CLI
- [ ] Configurar .env com credenciais Firebase

### Backend
- [ ] Criar estrutura de Cloud Functions
- [ ] Migrar endpoints de autenticação
- [ ] Migrar endpoints de transações
- [ ] Migrar endpoints de categorias
- [ ] Migrar endpoints de contas
- [ ] Migrar endpoints de relatórios
- [ ] Implementar CSV import com Storage
- [ ] Implementar triggers de limpeza
- [ ] Testar com Firebase Emulators
- [ ] Deploy Cloud Functions

### Frontend
- [ ] Instalar Firebase SDK
- [ ] Configurar firebase-config.ts
- [ ] Atualizar AuthContext
- [ ] Substituir API calls por Firestore SDK
- [ ] Atualizar Login component
- [ ] Atualizar Register component
- [ ] Atualizar Dashboard
- [ ] Atualizar Transactions
- [ ] Atualizar Categories
- [ ] Atualizar Accounts
- [ ] Atualizar Reports
- [ ] Atualizar Profile (upload para Storage)
- [ ] Testar com Emulators
- [ ] Deploy Firebase Hosting

### Security
- [ ] Implementar Firestore Security Rules
- [ ] Implementar Storage Security Rules
- [ ] Testar Rules com usuário comum
- [ ] Testar Rules com admin
- [ ] Validar isolamento de dados entre usuários

### Dados
- [ ] Criar script de migração
- [ ] Testar migração em ambiente de dev
- [ ] Validar integridade dos dados migrados
- [ ] Criar índices compostos no Firestore
- [ ] Executar migração de produção
- [ ] Validar dados em produção

### Monitoramento
- [ ] Configurar Firebase Analytics
- [ ] Configurar Firebase Crashlytics
- [ ] Configurar alertas de erro
- [ ] Configurar alertas de custo
- [ ] Dashboard de monitoramento

### Documentação
- [ ] Atualizar README com instruções Firebase
- [ ] Documentar estrutura de Collections
- [ ] Documentar Security Rules
- [ ] Documentar processo de deploy
- [ ] Guia de troubleshooting

---

## 💰 Estimativa de Custos Firebase

### Plano Spark (Gratuito)
- Firestore: 1GB storage, 50K leituras/dia, 20K escritas/dia
- Authentication: Ilimitado
- Storage: 5GB
- Cloud Functions: 125K invocações/mês, 40K GB-segundos
- Hosting: 10GB bandwidth

### Plano Blaze (Pay-as-you-go)
- Firestore: $0.18/GB storage, $0.06/100K leituras, $0.18/100K escritas
- Storage: $0.026/GB
- Cloud Functions: $0.40/milhão invocações, $0.0000025/GB-segundo
- Hosting: $0.15/GB após 10GB

**Estimativa para aplicação pequena-média (1000 usuários ativos):**
- Firestore: ~$5-15/mês
- Functions: ~$5-10/mês
- Storage: ~$1-3/mês
- **Total: $11-28/mês**

---

## 🔧 Comandos Úteis

```bash
# Instalar Firebase CLI
npm install -g firebase-tools

# Login
firebase login

# Inicializar projeto
firebase init

# Emulators (desenvolvimento local)
firebase emulators:start

# Deploy Functions
firebase deploy --only functions

# Deploy Hosting
firebase deploy --only hosting

# Deploy Firestore Rules
firebase deploy --only firestore:rules

# Deploy Storage Rules
firebase deploy --only storage

# Deploy completo
firebase deploy

# Logs de Functions
firebase functions:log
```

---

## 📚 Recursos e Referências

- [Firebase Documentation](https://firebase.google.com/docs)
- [Firestore Data Modeling](https://firebase.google.com/docs/firestore/data-model)
- [Security Rules Guide](https://firebase.google.com/docs/firestore/security/get-started)
- [Cloud Functions Python](https://firebase.google.com/docs/functions/get-started?gen=2nd#python)
- [Firebase Authentication](https://firebase.google.com/docs/auth)
- [Firebase Emulator Suite](https://firebase.google.com/docs/emulator-suite)

---

## ✅ Critérios de Sucesso

- [ ] Todos os endpoints funcionando via Cloud Functions
- [ ] Autenticação via Firebase Auth (Email/Password + Google OAuth)
- [ ] Todos os dados migrados com integridade preservada
- [ ] Security Rules implementadas e testadas
- [ ] Frontend 100% integrado com Firebase SDK
- [ ] Real-time listeners funcionando (opcional)
- [ ] CSV import via Storage funcionando
- [ ] Performance igual ou melhor que sistema anterior
- [ ] Monitoramento e alertas configurados
- [ ] Testes E2E passando
- [ ] Documentação completa atualizada
- [ ] Deploy em produção estável por 1 semana

---

## 🎯 Benefícios da Migração

1. **Escalabilidade Automática**: Firebase escala automaticamente
2. **Real-time**: Suporte nativo a listeners em tempo real
3. **Segurança**: Rules declarativas e Firebase Auth robusto
4. **Custo**: Pay-as-you-go, geralmente mais barato que servidores dedicados
5. **DevOps Simplificado**: Sem gerenciamento de servidores
6. **Performance Global**: CDN global para Hosting
7. **Monitoramento**: Analytics e Crashlytics integrados
8. **Mobile**: Fácil expansão para apps mobile (React Native)
9. **Offline Support**: Firestore suporta operações offline
10. **Backup Automático**: Backups gerenciados pelo Google

---

**🔥 PROMPT COMPLETO PARA MIGRAÇÃO FIREBASE GOOGLE**

*Utilize este documento como guia completo para migrar todo o projeto Alca Finanças para o ecossistema Firebase, seguindo as melhores práticas e garantindo segurança, performance e escalabilidade.*
