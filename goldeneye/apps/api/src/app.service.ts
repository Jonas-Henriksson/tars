import { Injectable } from '@nestjs/common';

@Injectable()
export class AppService {
  getStatus() {
    return { status: 'ok', name: 'goldeneye-api', version: '0.1.0' };
  }
}
