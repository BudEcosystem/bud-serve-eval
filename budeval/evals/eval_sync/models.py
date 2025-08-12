#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Database models for evaluation sync state tracking."""

from datetime import datetime
from uuid import uuid4

from budmicroframe.shared.psql_service import PSQLBase
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID


class EvalSyncState(PSQLBase):
    """Track evaluation dataset synchronization state and history."""

    __tablename__ = "eval_sync_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    manifest_version = Column(String(50), nullable=False)
    sync_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    sync_status = Column(String(20), nullable=False)  # 'completed', 'failed', 'in_progress'
    sync_metadata = Column(JSONB, nullable=True)  # Store manifest details, datasets synced, errors, etc.