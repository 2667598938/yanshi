import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from ..deps import get_db
from ..errors import ok
from ..models import Announcement, Config
from ..serializers import iso
from ..legal_text import LEGAL_VERSION, TERMS, PRIVACY, DISCLAIMER

router = APIRouter(prefix='/api/v1', tags=['public'])


def config_get(db, key, default=None):
    row = db.get(Config, key)
    if row is None:
        return default
    try:
        return json.loads(row.config_value)
    except (ValueError, TypeError):
        return row.config_value


@router.get('/config/public')
def public_config(request: Request, db=Depends(get_db)):
    return ok({
        'site_name': config_get(db, 'site_name', '研时'),
        'exam_date': config_get(db, 'exam_date', '2027-12-25'),
        'exam_year': config_get(db, 'exam_year', 2028),
        'registration_open': config_get(db, 'registration_open', False),
        'enabled_auth_channels': request.app.state.settings.enabled_auth_channels,
    })


@router.get('/legal')
def legal():
    return ok({'version': LEGAL_VERSION, 'terms': TERMS, 'privacy': PRIVACY,
               'disclaimer': DISCLAIMER})


@router.get('/announcements')
def active_announcements(db=Depends(get_db)):
    rows = db.scalars(select(Announcement).where(
        Announcement.is_active.is_(True)).order_by(
        Announcement.id.desc()).limit(10)).all()
    return ok([{'id': r.id, 'content': r.content, 'created_at': iso(r.created_at)}
               for r in rows])
