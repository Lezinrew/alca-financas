"""
Serviço de integração com Supabase Auth
"""
from typing import Dict, Any, Optional
from database.connection import get_supabase
from repositories.user_repository_supabase import UserRepository
import logging

logger = logging.getLogger(__name__)


class SupabaseAuthService:
    """Serviço para integrar Supabase Auth com a tabela users customizada"""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.user_repo = UserRepository()
    
    def sign_up(self, email: str, password: str, name: str) -> Dict[str, Any]:
        """
        Registra novo usuário no Supabase Auth e cria registro na tabela users
        
        Returns:
            {
                'user': {...},
                'session': {...},
                'access_token': '...',
                'refresh_token': '...'
            }
        """
        try:
            # 1. Criar usuário no Supabase Auth
            auth_response = self.supabase.auth.sign_up({
                'email': email,
                'password': password,
                'options': {
                    'data': {
                        'name': name
                    }
                }
            })
            
            if not auth_response.user:
                raise ValueError("Falha ao criar usuário no Supabase Auth")
            
            auth_user = auth_response.user
            auth_user_id = auth_user.id
            
            # 2. Criar registro na tabela users customizada
            user_data = {
                'id': auth_user_id,  # Usa o mesmo ID do Supabase Auth
                'email': email,
                'name': name,
                'settings': {
                    'currency': 'BRL',
                    'theme': 'light',
                    'language': 'pt'
                },
                'auth_providers': [{'provider': 'email', 'email_verified': auth_user.email_confirmed_at is not None}],
                'is_admin': False
            }
            
            # Verificar se já existe (pode acontecer em caso de retry)
            existing_user = self.user_repo.find_by_id(auth_user_id)
            if not existing_user:
                self.user_repo.create(user_data)
            
            # 3. Retornar dados formatados
            return {
                'user': {
                    'id': auth_user_id,
                    'email': email,
                    'name': name,
                    'email_verified': auth_user.email_confirmed_at is not None
                },
                'access_token': auth_response.session.access_token if auth_response.session else None,
                'refresh_token': auth_response.session.refresh_token if auth_response.session else None,
                'session': auth_response.session
            }
        except Exception as e:
            logger.error(f"Erro ao registrar usuário: {e}")
            raise
    
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Autentica usuário no Supabase Auth
        
        Returns:
            {
                'user': {...},
                'session': {...},
                'access_token': '...',
                'refresh_token': '...'
            }
        """
        try:
            # Autenticar no Supabase Auth
            auth_response = self.supabase.auth.sign_in_with_password({
                'email': email,
                'password': password
            })
            
            if not auth_response.user or not auth_response.session:
                raise ValueError("Credenciais inválidas")
            
            auth_user = auth_response.user
            auth_user_id = auth_user.id
            
            # Buscar dados customizados na tabela users
            custom_user = self.user_repo.find_by_id(auth_user_id)
            
            # Se não existir na tabela customizada, criar (pode acontecer se usuário foi criado diretamente no Supabase)
            if not custom_user:
                user_data = {
                    'id': auth_user_id,
                    'email': email,
                    'name': auth_user.user_metadata.get('name', email.split('@')[0]),
                    'settings': {
                        'currency': 'BRL',
                        'theme': 'light',
                        'language': 'pt'
                    },
                    'auth_providers': [{'provider': 'email', 'email_verified': auth_user.email_confirmed_at is not None}],
                    'is_admin': False
                }
                self.user_repo.create(user_data)
                custom_user = self.user_repo.find_by_id(auth_user_id)
            
            return {
                'user': {
                    'id': auth_user_id,
                    'email': email,
                    'name': custom_user.get('name') if custom_user else auth_user.user_metadata.get('name', email.split('@')[0]),
                    'email_verified': auth_user.email_confirmed_at is not None,
                    'settings': custom_user.get('settings', {}) if custom_user else {}
                },
                'access_token': auth_response.session.access_token,
                'refresh_token': auth_response.session.refresh_token,
                'session': auth_response.session
            }
        except Exception as e:
            logger.error(f"Erro ao fazer login: {e}")
            raise
    
    def get_user(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados do usuário autenticado
        
        Args:
            access_token: Token de acesso do Supabase
            
        Returns:
            Dados do usuário ou None
        """
        try:
            # Definir sessão no cliente Supabase
            self.supabase.auth.set_session(access_token=access_token, refresh_token='')
            
            # Obter usuário atual
            auth_user = self.supabase.auth.get_user(access_token)
            
            if not auth_user.user:
                return None
            
            auth_user_id = auth_user.user.id
            
            # Buscar dados customizados
            custom_user = self.user_repo.find_by_id(auth_user_id)
            
            if not custom_user:
                return None
            
            return {
                'id': auth_user_id,
                'email': auth_user.user.email,
                'name': custom_user.get('name'),
                'settings': custom_user.get('settings', {}),
                'is_admin': custom_user.get('is_admin', False),
                'email_verified': auth_user.user.email_confirmed_at is not None
            }
        except Exception as e:
            logger.error(f"Erro ao obter usuário: {e}")
            return None
    
    def refresh_session(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Renova a sessão usando refresh token
        
        Returns:
            Nova sessão com access_token e refresh_token
        """
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
            
            if not response.session:
                return None
            
            return {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'session': response.session
            }
        except Exception as e:
            logger.error(f"Erro ao renovar sessão: {e}")
            return None
    
    def sign_out(self, access_token: str):
        """Faz logout do usuário"""
        try:
            self.supabase.auth.set_session(access_token=access_token, refresh_token='')
            self.supabase.auth.sign_out()
        except Exception as e:
            logger.error(f"Erro ao fazer logout: {e}")



