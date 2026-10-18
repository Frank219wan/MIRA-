import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "../ui/button";
import { JourneyProgress } from "./JourneyProgress";

export function JourneyNavigation({
  backTo,
  progress,
  backLabel = "上一步",
}: {
  backTo: string;
  progress: number;
  backLabel?: string;
}) {
  return (
    <div className="journey-navigation">
      <Button asChild variant="tertiary" className="journey-back">
        <Link to={backTo}>
          <ArrowLeft size={15} aria-hidden="true" />
          {backLabel}
        </Link>
      </Button>
      <JourneyProgress value={progress} />
    </div>
  );
}
