import { Navigate, Route, Routes } from "react-router-dom";
import { lazy, Suspense } from "react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { RoleRoute } from "@/components/auth/RoleRoute";
import { AppLayout } from "@/layouts/AppLayout";
import { AdminLayout } from "@/layouts/AdminLayout";
import { PageSkeleton } from "@/components/common/PageSkeleton";
import RootRedirect from "@/pages/RootRedirect";
import Login from "@/pages/auth/Login";
import Cadastro from "@/pages/auth/Cadastro";
import VincularTelegram from "@/pages/auth/VincularTelegram";
import Forbidden from "@/pages/Forbidden";
import NotFound from "@/pages/NotFound";

// User area
const UserDashboard = lazy(() => import("@/pages/app/Dashboard"));
const UserTransacoes = lazy(() => import("@/pages/app/Transacoes"));
const UserTransacaoDetalhe = lazy(() => import("@/pages/app/TransacaoDetalhe"));
const UserPendencias = lazy(() => import("@/pages/app/Pendencias"));
const UserRelatorios = lazy(() => import("@/pages/app/Relatorios"));
const UserConfiguracoes = lazy(() => import("@/pages/app/Configuracoes"));

// Admin area
const AdminDashboard = lazy(() => import("@/pages/admin/Dashboard"));
const AdminUsuarios = lazy(() => import("@/pages/admin/Usuarios"));
const AdminTransacoes = lazy(() => import("@/pages/admin/Transacoes"));
const AdminCategorias = lazy(() => import("@/pages/admin/Categorias"));
const AdminAtividade = lazy(() => import("@/pages/admin/Atividade"));
const AdminPerformance = lazy(() => import("@/pages/admin/Performance"));
const AdminErros = lazy(() => import("@/pages/admin/Erros"));
const AdminIntegracoes = lazy(() => import("@/pages/admin/Integracoes"));
const AdminConfiguracoes = lazy(() => import("@/pages/admin/Configuracoes"));

export default function App() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<Login />} />
        <Route path="/cadastro" element={<Cadastro />} />
        <Route path="/vincular-telegram" element={<VincularTelegram />} />

        <Route
          path="/app"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<UserDashboard />} />
          <Route path="transacoes" element={<UserTransacoes />} />
          <Route path="transacoes/:id" element={<UserTransacaoDetalhe />} />
          <Route path="pendencias" element={<UserPendencias />} />
          <Route path="relatorios" element={<UserRelatorios />} />
          <Route path="configuracoes" element={<UserConfiguracoes />} />
        </Route>

        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <RoleRoute role="ADMIN">
                <AdminLayout />
              </RoleRoute>
            </ProtectedRoute>
          }
        >
          <Route index element={<AdminDashboard />} />
          <Route path="usuarios" element={<AdminUsuarios />} />
          <Route path="transacoes" element={<AdminTransacoes />} />
          <Route path="categorias" element={<AdminCategorias />} />
          <Route path="atividade" element={<AdminAtividade />} />
          <Route path="performance" element={<AdminPerformance />} />
          <Route path="erros" element={<AdminErros />} />
          <Route path="integracoes" element={<AdminIntegracoes />} />
          <Route path="configuracoes" element={<AdminConfiguracoes />} />
        </Route>

        <Route path="/403" element={<Forbidden />} />
        <Route path="/404" element={<NotFound />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Routes>
    </Suspense>
  );
}
