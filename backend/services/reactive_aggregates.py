"""Rebuild derived reactive totals from retained jobs; shared by upload and deletion."""
from sqlalchemy import Date, Integer, and_, case, cast, extract, func, insert, select
from models.asset import ReactiveAggregate, ReactiveJobRecord as Job


def rebuild_reactive_aggregates(db, asset_ids):
    """Accept IDs or a scoped SELECT. Does not commit the caller's transaction."""
    db.query(ReactiveAggregate).filter(ReactiveAggregate.asset_id.in_(asset_ids)).delete(synchronize_session=False)

    def days_between(end, start):
        if db.bind.dialect.name == "sqlite":
            return cast(func.julianday(func.date(end)) - func.julianday(func.date(start)), Integer)
        return cast(end, Date) - cast(start, Date)

    def count_if(condition):
        return func.sum(case((condition, 1), else_=0))

    year = cast(extract("year", Job.job_entry_date), Integer)
    fields = {
        "asset_id": Job.asset_id,
        "nsg_ref": func.min(Job.nsg_ref),
        "year": year,
        "total_jobs_raised": func.count(),
        "emergency_jobs_2hr": count_if(Job.priority_category == 1),
        "urgent_jobs_24hr": count_if(Job.priority_category == 2),
        "jobs_5day": count_if(Job.priority_category == 3),
        "jobs_28day": count_if(Job.priority_category == 4),
        **{f"{category}_count": count_if(Job.job_type_category == category)
           for category in ("pothole", "patching", "edge", "drainage", "other")},
        "most_recent_defect_date": func.max(Job.job_entry_date),
        "days_since_most_recent_defect": days_between(func.current_date(), func.max(Job.job_entry_date)),
        "jobs_completed": count_if(Job.actual_comp_date.isnot(None)),
        "jobs_outstanding": count_if(Job.actual_comp_date.is_(None)),
        "mean_days_to_completion": func.avg(case(
            (and_(Job.actual_comp_date.isnot(None), Job.actual_comp_date >= Job.job_entry_date),
             days_between(Job.actual_comp_date, Job.job_entry_date)), else_=None)),
        "oldest_outstanding_days": days_between(func.current_date(), func.min(case(
            (Job.actual_comp_date.is_(None), Job.job_entry_date), else_=None))),
        "rebuilt_at": func.now(),
    }
    source = select(*fields.values()).where(
        Job.asset_id.in_(asset_ids), Job.job_entry_date.isnot(None)
    ).group_by(Job.asset_id, year)
    db.execute(insert(ReactiveAggregate).from_select(list(fields), source))
