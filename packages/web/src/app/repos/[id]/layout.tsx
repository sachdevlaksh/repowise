import { getRepo } from "@/lib/api/repos";

interface RepoLayoutProps {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}

export default async function RepoLayout({ children, params }: RepoLayoutProps) {
  const { id } = await params;
  // Repo data is fetched here so child pages can use it via server props.
  // The sidebar is in the root layout and already has access to all repos.
  // This layout just renders children — individual pages fetch their own data.
  return <>{children}</>;
}
