import React, { useCallback, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CategoryNameSuggestions, CategoryRelatedExamples } from './CategoryAssist';
import { getTemplateForSuggestionText } from '../../utils/categoryAssist';
import { AppDialog } from '../shared/AppDialog';
import { availableColors, availableIcons } from './categoryExampleFile';
import { CATEGORY_SAVE_ERROR, type Category, type CategoryPayload, type CategoryType } from './types';

interface CategoryFormProps {
  onHide: () => void;
  /** Deve lançar em caso de falha; o formulário permanece aberto com mensagem fixa. */
  onSubmit: (data: CategoryPayload) => Promise<void> | void;
  category?: Partial<Category> | null;
}

type FormData = {
  name: string;
  type: CategoryType;
  color: string;
  icon: string;
  description: string;
};

function initialValues(category?: Partial<Category> | null): FormData {
  return {
    name: category?.name || '',
    type: category?.type || 'expense',
    color: category?.color || '#6366f1',
    icon: category?.icon || 'circle',
    description: category?.description || '',
  };
}

const labelClass = 'mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200';

/** Monte uma instância nova a cada abertura (o estado inicial vem de `category`). */
const CategoryForm: React.FC<CategoryFormProps> = ({ onHide, onSubmit, category }) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<FormData>(() => initialValues(category));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const submitting = useRef(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const prefix = useId();
  const id = (field: string) => `${prefix}-${field}`;

  const setField = (name: keyof FormData, value: string) => {
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setField(e.target.name as keyof FormData, e.target.value);
  };

  const applyNameSuggestion = useCallback((text: string) => {
    const isCreate = !category;
    setFormData(prev => {
      const template = getTemplateForSuggestionText(prev.type, text);
      const next: FormData = { ...prev, name: text };
      if (isCreate && template) {
        next.color = template.color ?? prev.color;
        next.icon = template.icon ?? prev.icon;
        if (!prev.description.trim() && template.descriptionHint) next.description = template.descriptionHint;
      }
      return next;
    });
    setError('');
    requestAnimationFrame(() => {
      const el = nameInputRef.current;
      if (!el) return;
      el.focus();
      const end = el.value.length;
      el.setSelectionRange(end, end);
    });
  }, [category]);

  const appendExampleToDescription = useCallback((tag: string) => {
    const piece = tag.trim();
    if (!piece) return;
    setFormData(prev => {
      const d = prev.description.trim();
      if (!d) return { ...prev, description: piece };
      if (d.toLowerCase().includes(piece.toLowerCase())) return prev;
      return { ...prev, description: `${d}; ${piece}` };
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting.current) return;
    setError('');

    const trimmedName = formData.name.trim();
    if (!trimmedName) {
      setError('Informe o nome da categoria.');
      nameInputRef.current?.focus();
      return;
    }
    if (formData.type !== 'income' && formData.type !== 'expense') {
      setError('Selecione o tipo da categoria.');
      return;
    }

    const submitData: CategoryPayload = {
      name: trimmedName,
      type: formData.type,
      color: formData.color || '#6366f1',
      icon: formData.icon || 'circle',
      description: formData.description.trim(),
    };

    submitting.current = true;
    setSaving(true);
    try {
      await onSubmit(submitData);
    } catch {
      setError(CATEGORY_SAVE_ERROR);
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  };

  const close = () => { if (!submitting.current) onHide(); };

  return (
    <AppDialog title={category ? t('categories.edit') : t('categories.add')} onClose={close} busy={saving} initialFocus={nameInputRef} size="lg">
      <form onSubmit={handleSubmit} className="p-4" noValidate>
        {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}

        {/* Prévia */}
        <div className="mb-4 text-center" aria-hidden="true">
          <div className="mx-auto mb-2 flex h-20 w-20 items-center justify-center rounded-full" style={{ backgroundColor: formData.color }}>
            <i className={`bi bi-${formData.icon} text-white`} style={{ fontSize: '2rem' }}></i>
          </div>
          <p className="font-semibold text-slate-900 dark:text-white">{formData.name || 'Nome da categoria'}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">{formData.type === 'income' ? t('categories.income') : t('categories.expense')}</p>
        </div>

        <fieldset disabled={saving} className="space-y-4">
          <div>
            <label htmlFor={id('name')} className={labelClass}>{t('categories.name')} *</label>
            <input ref={nameInputRef} type="text" id={id('name')} name="name" value={formData.name} onChange={handleChange} required
              placeholder="Ex: Alimentação, Salário, etc." autoComplete="off" className="native-input-themed min-h-[44px] w-full" />
            <CategoryNameSuggestions className="mt-2" kind={formData.type} nameQuery={formData.name} currentName={formData.name} disabled={saving} onSelect={applyNameSuggestion} />
          </div>

          <div>
            <label htmlFor={id('description')} className={labelClass}>Descrição (opcional)</label>
            <textarea id={id('description')} name="description" value={formData.description} onChange={handleChange} rows={3}
              placeholder="Ex: Doações recebidas, contribuições, etc." className="native-input-themed w-full" />
            <CategoryRelatedExamples className="mt-2" kind={formData.type} currentName={formData.name} disabled={saving} onExampleTagClick={appendExampleToDescription} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <fieldset>
              <legend className={labelClass}>{t('categories.type')} *</legend>
              <div className="flex gap-2">
                {(['income', 'expense'] as const).map(type => {
                  const selected = formData.type === type;
                  const tone = type === 'income' ? 'border-emerald-600 bg-emerald-600 text-white' : 'border-red-600 bg-red-600 text-white';
                  return (
                    <label key={type} htmlFor={id(`type-${type}`)}
                      className={`flex min-h-[44px] flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg border text-sm font-medium focus-within:ring-2 focus-within:ring-indigo-600 focus-within:ring-offset-2 ${selected ? tone : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700'}`}>
                      <input type="radio" id={id(`type-${type}`)} name="type" value={type} checked={selected} onChange={handleChange} className="sr-only" />
                      <i className={`bi ${type === 'income' ? 'bi-arrow-up-circle' : 'bi-arrow-down-circle'}`} aria-hidden="true"></i>
                      {t(`categories.${type}`)}
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <fieldset>
              <legend className={labelClass}>{t('categories.color')}</legend>
              <div className="mb-2 flex flex-wrap gap-2">
                {availableColors.map(color => (
                  <button key={color} type="button" aria-label={`Cor ${color}`} aria-pressed={formData.color === color}
                    className={`h-9 w-9 rounded-full border-2 ${formData.color === color ? 'border-slate-900 ring-2 ring-slate-400 ring-offset-2 dark:border-white' : 'border-slate-200 dark:border-slate-600'}`}
                    style={{ backgroundColor: color }} onClick={() => setField('color', color)} />
                ))}
              </div>
              <label htmlFor={id('color')} className="text-xs text-slate-500 dark:text-slate-400">Cor personalizada</label>
              <input type="color" id={id('color')} name="color" value={formData.color} onChange={handleChange} className="ml-2 h-9 w-12 cursor-pointer rounded border border-slate-300 dark:border-slate-600" />
            </fieldset>
          </div>

          <fieldset>
            <legend className={labelClass}>{t('categories.icon')}</legend>
            <div className="flex flex-wrap gap-1">
              {availableIcons.map(icon => (
                <button key={icon} type="button" aria-label={`Ícone ${icon}`} aria-pressed={formData.icon === icon}
                  className={`flex h-11 w-11 items-center justify-center rounded-lg border text-lg ${formData.icon === icon ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700'}`}
                  onClick={() => setField('icon', icon)}>
                  <i className={`bi bi-${icon}`}></i>
                </button>
              ))}
            </div>
          </fieldset>
        </fieldset>

        <div className="mt-5 flex justify-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-700">
          <button type="button" onClick={close} disabled={saving} className="min-h-[44px] rounded-lg border border-slate-300 px-4 text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600 disabled:opacity-50 dark:border-slate-600 dark:text-slate-100">{t('common.cancel')}</button>
          <button type="submit" disabled={saving} className="min-h-[44px] rounded-lg bg-indigo-600 px-4 font-medium text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50">{saving ? 'Salvando…' : t('common.save')}</button>
        </div>
      </form>
    </AppDialog>
  );
};

export default CategoryForm;
