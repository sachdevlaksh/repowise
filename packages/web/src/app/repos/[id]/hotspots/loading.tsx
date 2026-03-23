import { Skeleton } from "@/components/ui/skeleton";

export default function HotspotsLoading() {
  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-6xl">
      <div>
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-4 w-52 mt-1.5" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-lg" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Skeleton className="h-[400px] rounded-lg" />
        </div>
        <Skeleton className="h-[300px] rounded-lg" />
      </div>
    </div>
  );
}
