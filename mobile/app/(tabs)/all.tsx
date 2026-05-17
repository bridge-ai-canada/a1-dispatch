import { JobList } from "./index";
export default function AllJobs() {
    return <JobList scope="all" emptyLabel="No jobs assigned to you yet." />;
}
