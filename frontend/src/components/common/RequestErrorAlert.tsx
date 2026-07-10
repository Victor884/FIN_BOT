import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ApiError } from "@/api/client";

export function RequestErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const status = error instanceof ApiError ? error.status : undefined;
  const message = error instanceof Error ? error.message : "Erro desconhecido";
  const requestId = error instanceof ApiError ? error.request_id : undefined;
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Não foi possível carregar os dados{status ? ` (HTTP ${status})` : ""}</AlertTitle>
      <AlertDescription className="space-y-2">
        <div>{message}</div>
        {requestId && <div className="text-xs opacity-80">Request ID: {requestId}</div>}
        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw className="mr-2 h-3 w-3" /> Tentar novamente
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
