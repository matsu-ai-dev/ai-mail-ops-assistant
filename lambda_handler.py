from mangum import Mangum

from api_app import app


handler = Mangum(app)
