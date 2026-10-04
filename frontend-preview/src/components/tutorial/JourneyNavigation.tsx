import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "../ui/button";
import { JourneyProgress } from "./JourneyProgress";

export function JourneyNavigation({
  backTo,
  progress,
}: {
  backTo: string;
  progress: number;
}) {
  return (
    <div className="journey-navigation">
      <Button asChild variant="tertiary" className="journey-back">
        <Link to={backTo}>
          <ArrowLeft size={15} aria-hidden="true" />
          上一步
        </Link>
      </Button>
      <JourneyProgress value={progress} />
    </div>
  );
}
