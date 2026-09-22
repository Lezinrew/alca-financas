import { AppDialog, type AppDialogProps } from '../shared/AppDialog';
import './financial-expenses.css';

export type ExpenseDialogProps = Omit<AppDialogProps, 'size'>;

/** Diálogo compartilhado com os tokens visuais da aba Contas a pagar aplicados ao conteúdo. */
export function ExpenseDialog({ children, ...props }: ExpenseDialogProps) {
  return <AppDialog {...props}><div className="payables">{children}</div></AppDialog>;
}
