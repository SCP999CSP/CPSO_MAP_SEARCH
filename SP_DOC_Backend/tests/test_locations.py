import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.dependencies import get_session
from app.main import app
from app.models import Doctor, DoctorAddress

TORONTO = {"north": 43.86, "south": 43.58, "east": -79.11, "west": -79.64}


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Doctor(
                cpso_number="111",
                full_name="Dr Downtown",
                specialties="Neurology | Rheumatology",
                gender="Female",
            )
        )
        session.add(Doctor(cpso_number="222", full_name="Dr Ottawa"))
        session.add(Doctor(cpso_number="333", full_name="Dr Unknown"))
        session.add(
            DoctorAddress(
                cpso_number="111",
                full_address="100 Queen St W, Toronto",
                phone="416-555-0100",
                latitude=43.6532,
                longitude=-79.3832,
            )
        )
        session.add(
            DoctorAddress(cpso_number="222", latitude=45.4215, longitude=-75.6972)
        )
        session.add(DoctorAddress(cpso_number="333"))
        session.commit()
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_returns_only_locations_inside_bounds(client: TestClient):
    response = client.get("/api/locations", params=TORONTO)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["cpso_number"] == "111"
    assert data[0]["full_name"] == "Dr Downtown"
    assert data[0]["full_address"] == "100 Queen St W, Toronto"
    assert data[0]["specialties"] == "Neurology | Rheumatology"
    assert data[0]["gender"] == "Female"
    assert data[0]["phone"] == "416-555-0100"
    assert set(data[0]) == {
        "id",
        "cpso_number",
        "full_name",
        "specialties",
        "gender",
        "medical_school",
        "languages_spoken",
        "graduate_data",
        "full_address",
        "city",
        "province",
        "postal_code",
        "phone",
        "fax",
        "latitude",
        "longitude",
    }


def test_empty_when_no_locations_in_bounds(client: TestClient):
    params = {"north": 10, "south": 0, "east": 10, "west": 0}
    response = client.get("/api/locations", params=params)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "override",
    [{"north": 91}, {"south": -91}, {"east": 181}, {"west": -181}, {"north": "abc"}],
)
def test_rejects_out_of_range_coordinates(client: TestClient, override: dict):
    response = client.get("/api/locations", params={**TORONTO, **override})

    assert response.status_code == 422


def test_rejects_missing_parameter(client: TestClient):
    params = {k: v for k, v in TORONTO.items() if k != "east"}
    response = client.get("/api/locations", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "override",
    [{"south": 44.0, "north": 43.0}, {"west": -79.0, "east": -80.0}],
)
def test_rejects_inverted_bounds(client: TestClient, override: dict):
    response = client.get("/api/locations", params={**TORONTO, **override})

    assert response.status_code == 422
