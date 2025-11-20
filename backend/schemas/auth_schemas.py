from pydantic import BaseModel, EmailStr, Field, field_validator

class UserRegisterSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Nome do usuário")
    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., min_length=6, description="Senha do usuário")

    @field_validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Nome não pode ser vazio')
        return v.strip()

class UserLoginSchema(BaseModel):
    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., description="Senha do usuário")

class RefreshTokenSchema(BaseModel):
    refresh_token: str = Field(..., description="Token de atualização")
