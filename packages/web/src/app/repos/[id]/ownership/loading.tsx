import { Skeleton } from "@/components/ui/skeleton";

export default function OwnershipLoading() {
  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-6xl">
      <div>
        <Skeleton className="h-7 w-36" />
        <Skeleton className="h-4 w-52 mt-1.5" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-9 w-36" />
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Skeleton className="h-[400px] rounded-lg" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-[200px] rounded-lg" />
          <Skeleton className="h-[160px] rounded-lg" />
        </div>
      </div>
    </div>
  );
}
