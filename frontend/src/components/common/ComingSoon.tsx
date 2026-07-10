import { PageHeader } from "./PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Wrench } from "lucide-react";

export function ComingSoon({ title, description }: { title: string; description?: string }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Card>
        <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <Wrench className="h-10 w-10 text-muted-foreground" />
          <div className="text-sm text-muted-foreground">
            Esta tela faz parte da Etapa 2 da entrega. A estrutura de rota, proteção e navegação já
            estão prontas — os componentes que consomem os endpoints reais serão implementados no
            próximo ciclo.
          </div>
        </CardContent>
      </Card>
    </>
  );
}
